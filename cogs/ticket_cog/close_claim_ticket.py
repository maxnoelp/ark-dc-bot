import discord
import os
import asyncio
import logging
from datetime import datetime, timezone
from discord import ui
from bot.logs_to_channel import log_to_channel
from dotenv import load_dotenv

load_dotenv()

# Konfiguration
TICKET_ARCHIVE_CHANNEL_NAME = os.getenv(
    "TICKET_ARCHIVE_CHANNEL_NAME"
)  # bevorzugt ein einzelner Textchannel
TICKET_ARCHIVE_CATEGORY_NAME = os.getenv(
    "TICKET_ARCHIVE_CATEGORY_NAME"
)  # optional Kategorie
TRANSCRIPT_FOLDER = os.getenv("TRANSCRIPT_FOLDER") or "transcripts"

DELETE_DELAY = int(os.getenv("TICKET_DELETE_DELAY_SECONDS") or 5)  # für Tests z.B. 5
DELETE_TRANSCRIPT_AFTER_ARCHIVE = (
    False  # auf True setzen, wenn du die Datei nach Upload löschen willst
)

logger = logging.getLogger("ticket.closeview")


class CloseView(ui.View):
    """Claim / Close-Buttons für jede Ticket-Nachricht mit robustem Close & garantiertem Lösch-Task."""

    def __init__(self, requester: discord.Member | None = None):
        super().__init__(timeout=None)
        self.requester = requester
        logger.debug("CloseView init requester=%s", requester)

    # ------------------- Claim -------------------------------------------------
    @ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim_button",
    )
    async def claim_button(self, interaction: discord.Interaction, button: ui.Button):
        corr_id = interaction.id
        guild = interaction.guild
        channel = interaction.channel
        claimer = interaction.user

        logger.debug("[%s] Claim click by %s in #%s", corr_id, claimer, channel)

        try:
            if not any(r.permissions.administrator for r in claimer.roles):
                logger.info("[%s] Claim denied (no admin) user=%s", corr_id, claimer)
                await interaction.response.send_message(
                    "❌ Nur Admins können Tickets claimen.", ephemeral=True
                )
                await log_to_channel(
                    guild, f"{claimer.mention} wollte claimen (keine Rechte)."
                )
                return

            # Andere Admins (außer Claimer) stummschalten
            for m in guild.members:
                if m != claimer and any(r.permissions.administrator for r in m.roles):
                    try:
                        await channel.set_permissions(m, send_messages=False)
                        logger.debug("[%s] Admin %s muted", corr_id, m)
                    except Exception as e:
                        logger.warning(
                            "[%s] set_permissions mute %s: %s", corr_id, m, e
                        )

            await channel.set_permissions(
                claimer, send_messages=True, read_message_history=True
            )
            logger.debug("[%s] Claimer write perms set", corr_id)

            button.disabled = True
            try:
                await interaction.message.edit(view=self)
                logger.debug("[%s] Claim button disabled", corr_id)
            except Exception as e:
                logger.warning("[%s] Could not disable claim button: %s", corr_id, e)

            await interaction.response.send_message(
                f"🤺 {claimer.mention} hat das Ticket übernommen."
            )
            await log_to_channel(
                guild, f"{claimer.mention} hat {channel.name} geclaimt."
            )
            logger.info("[%s] Claim success", corr_id)

        except Exception as e:
            logger.exception("[%s] Unexpected error in claim: %s", corr_id, e)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Unerwarteter Fehler beim Claim.", ephemeral=True
                )

    # ------------------- Close -------------------------------------------------
    @ui.button(
        label="Ticket schließen & löschen",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_button",
    )
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        corr_id = interaction.id
        channel: discord.TextChannel = interaction.channel
        guild = interaction.guild
        closer = interaction.user

        logger.debug(
            "[%s] Close click user=%s channel=%s guild=%s",
            corr_id,
            closer,
            channel,
            guild,
        )

        # Flag ob wir am Ende löschen sollen
        should_delete = False
        transcript_path = None
        archive_channel: discord.TextChannel | None = None

        try:
            # Sobald wir in den Close-Prozess einsteigen, wollen wir letztlich löschen.
            should_delete = True

            requester = self.requester or self._guess_requester(channel)
            logger.debug("[%s] Requester resolved: %s", corr_id, requester)

            if requester:
                try:
                    await channel.set_permissions(requester, send_messages=False)
                    logger.debug("[%s] Requester muted", corr_id)
                except Exception as e:
                    logger.warning("[%s] Could not mute requester: %s", corr_id, e)

            if not channel.name.startswith("closed-"):
                new_name = f"closed-{channel.name}"
                try:
                    await channel.edit(name=new_name, reason="Ticket geschlossen")
                    logger.debug("[%s] Channel renamed -> %s", corr_id, new_name)
                except Exception as e:
                    logger.warning("[%s] Rename failed: %s", corr_id, e)

            # Transcript
            try:
                transcript_path = await self._save_transcript(channel, corr_id=corr_id)
                logger.info("[%s] Transcript saved: %s", corr_id, transcript_path)
            except Exception as e:
                logger.exception("[%s] Transcript failed: %s", corr_id, e)
                transcript_path = None

            # Archiv-Ziel finden
            archive_channel = await self._resolve_archive_channel(guild, corr_id)
            if archive_channel is None:
                logger.warning(
                    "[%s] Kein Archiv-Channel gefunden – Ticket wird dennoch gelöscht (Delay %ss).",
                    corr_id,
                    DELETE_DELAY,
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"⚠️ Kein Archiv-Channel gefunden. Lösche Ticket in {DELETE_DELAY}s trotzdem.",
                        ephemeral=True,
                    )
            else:
                # Archiv-Eintrag senden
                embed = discord.Embed(
                    title="📁 Archiviertes Ticket",
                    color=discord.Color.dark_grey(),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(
                    name="👤 User",
                    value=requester.mention if requester else "unbekannt",
                    inline=True,
                )
                embed.add_field(name="🎟️ Ticket", value=channel.name, inline=True)
                embed.add_field(name="🔒 Closed by", value=closer.mention, inline=True)
                embed.set_footer(
                    text="Transkript im Anhang"
                    if transcript_path
                    else "Kein Transkript"
                )

                files = []
                if transcript_path and os.path.exists(transcript_path):
                    try:
                        files.append(
                            discord.File(
                                transcript_path,
                                filename=os.path.basename(transcript_path),
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            "[%s] Could not attach transcript: %s", corr_id, e
                        )

                try:
                    await archive_channel.send(embed=embed, files=files)
                    logger.info(
                        "[%s] Archiv-Eintrag gesendet in %s", corr_id, archive_channel
                    )
                except Exception as e:
                    logger.exception("[%s] Archiv send failed: %s", corr_id, e)

            # Button deaktivieren
            try:
                button.disabled = True
                await interaction.message.edit(view=self)
                logger.debug("[%s] Close button disabled", corr_id)
            except Exception as e:
                logger.warning("[%s] Could not disable close button: %s", corr_id, e)

            # Ephemeral Antwort
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        f"✅ Ticket archiviert. Channel wird in {DELETE_DELAY}s gelöscht.",
                        ephemeral=True,
                    )
                except Exception as e:
                    logger.warning("[%s] Ephemeral response failed: %s", corr_id, e)

            # message_store austragen (optional best effort)
            try:
                from bot import message_store

                message_store.remove_ticket(guild.id, channel.id)
                logger.debug("[%s] Ticket removed from message_store", corr_id)
            except Exception as e:
                logger.warning(
                    "[%s] message_store remove_ticket failed: %s", corr_id, e
                )

        except Exception as e:
            logger.exception("[%s] Unexpected error in close handler: %s", corr_id, e)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Unerwarteter Fehler beim Schließen.", ephemeral=True
                )
        finally:
            if should_delete:
                # Lösch-Task planen
                async def _del():
                    try:
                        logger.debug(
                            "[%s] Wait %ss before deletion...", corr_id, DELETE_DELAY
                        )
                        await asyncio.sleep(DELETE_DELAY)
                        logger.debug("[%s] Deleting channel now...", corr_id)
                        await channel.delete(reason="Ticket geschlossen & archiviert")
                        logger.info("[%s] Channel deleted", corr_id)
                    except discord.Forbidden:
                        logger.error("[%s] Forbidden: cannot delete channel.", corr_id)
                        await log_to_channel(
                            guild, f"❌ Kann {channel.name} nicht löschen (Rechte)."
                        )
                    except discord.NotFound:
                        logger.debug("[%s] Channel already gone.", corr_id)
                    except Exception as e_inner:
                        logger.exception(
                            "[%s] Error deleting channel: %s", corr_id, e_inner
                        )
                    finally:
                        # Optional Transcript aufräumen
                        if (
                            DELETE_TRANSCRIPT_AFTER_ARCHIVE
                            and transcript_path
                            and os.path.exists(transcript_path)
                        ):
                            try:
                                os.remove(transcript_path)
                                logger.debug("[%s] Transcript file removed.", corr_id)
                            except Exception as e_rem:
                                logger.warning(
                                    "[%s] Could not remove transcript: %s",
                                    corr_id,
                                    e_rem,
                                )

                logger.debug(
                    "[%s] Scheduling deletion task (delay=%s)", corr_id, DELETE_DELAY
                )
                asyncio.create_task(_del())
            else:
                logger.debug(
                    "[%s] should_delete=False -> no deletion scheduled", corr_id
                )

    # ------------------- Helper: Archiv-Channel finden / erzeugen -------------------
    async def _resolve_archive_channel(
        self, guild: discord.Guild, corr_id
    ) -> discord.TextChannel | None:
        """
        Priorität:
        1. Expliziter Archiv-Textchannel (TICKET_ARCHIVE_CHANNEL_NAME)
        2. Falls nicht vorhanden & Kategorie gesetzt -> Channel in Kategorie anlegen (falls Rechte)
        3. Falls nur Kategorie existiert, aber kein Channel-Name konfiguriert -> erstellt 'ticket-archiv-log'
        4. None zurückgeben, wenn alles fehlschlägt
        """
        # 1. Direkt definierter Archiv-Textchannel
        if TICKET_ARCHIVE_CHANNEL_NAME:
            ch = discord.utils.get(
                guild.text_channels, name=TICKET_ARCHIVE_CHANNEL_NAME
            )
            if ch:
                logger.debug("[%s] Found archive channel (direct) %s", corr_id, ch)
                return ch

        # 2. Kategorie?
        if TICKET_ARCHIVE_CATEGORY_NAME:
            cat = discord.utils.get(guild.categories, name=TICKET_ARCHIVE_CATEGORY_NAME)
            if cat:
                # Versuchen, existierenden passenden Channel in der Kategorie zu finden
                for tch in cat.text_channels:
                    if tch.name.startswith("ticket-archiv") or tch.name.startswith(
                        "archiv"
                    ):
                        logger.debug(
                            "[%s] Found existing channel in category: %s", corr_id, tch
                        )
                        return tch
                # Erstellen
                if guild.me.guild_permissions.manage_channels:
                    try:
                        new_ch = (
                            guild.create_text_channel
                        )  # (nicht await – wir prüfen gleich)
                    except AttributeError:
                        return None
                    try:
                        return asyncio.get_running_loop().run_until_complete(
                            guild.create_text_channel(
                                "ticket-archiv-log",
                                category=cat,
                                reason="Ticket Archiv Log Channel Auto",
                            )
                        )
                    except RuntimeError:
                        # Wir sind in async Kontext, normal await:
                        pass
                    except Exception as e:
                        logger.warning(
                            "[%s] Could not create channel in category: %s", corr_id, e
                        )
                else:
                    logger.warning(
                        "[%s] No manage_channels perms to create archive channel.",
                        corr_id,
                    )
        return None

    # ------------------- Helper: Requester schätzen -------------------
    def _guess_requester(self, ch: discord.TextChannel) -> discord.Member | None:
        try:
            uid = int(ch.name.split("-")[-1])
            member = ch.guild.get_member(uid)
            logger.debug("Guess requester in %s -> %s", ch, member)
            return member
        except Exception:
            logger.debug("Guess requester failed for %s", ch)
            return None

    # ------------------- Helper: Transcript -------------------
    async def _save_transcript(self, ch: discord.TextChannel, corr_id=None) -> str:
        corr_id = corr_id or "NA"
        os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)
        path = os.path.join(TRANSCRIPT_FOLDER, f"{ch.name}.txt")
        logger.debug("[%s] Transcript start channel=%s path=%s", corr_id, ch, path)
        line_count = 0
        try:
            with open(path, "w", encoding="utf-8") as f:
                async for m in ch.history(limit=None, oldest_first=True):
                    ts = m.created_at.strftime("%Y-%m-%d %H:%M")
                    author = f"{m.author.name}#{m.author.discriminator}"
                    content = m.content.strip() if m.content else ""
                    if not content:
                        if m.attachments:
                            content = (
                                "[ATTACHMENT "
                                + ", ".join(a.filename for a in m.attachments)
                                + "]"
                            )
                        elif m.embeds:
                            content = "[EMBED]"
                        else:
                            content = "[LEER]"
                    f.write(f"[{ts}] {author}: {content}\n")
                    line_count += 1
            logger.debug("[%s] Transcript done lines=%d", corr_id, line_count)
            return path
        except Exception as e:
            logger.exception("[%s] Transcript error: %s", corr_id, e)
            raise
