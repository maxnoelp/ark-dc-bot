import discord
import asyncio
import os
import time
import logging
from dotenv import load_dotenv
from discord import ui
from cogs.ticket_cog.close_claim_ticket import CloseView
from bot import message_store

load_dotenv()
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME") or "tickets"

logger = logging.getLogger("ticket.modal")


class TicketModal(ui.Modal, title="🎫 Ticket erstellen"):
    anliegen = ui.TextInput(
        label="Was ist dein Anliegen?",
        style=discord.TextStyle.paragraph,
        max_length=1900,
    )

    async def on_submit(self, interaction: discord.Interaction):
        start_ts = time.perf_counter()
        corr_id = interaction.id  # Korrelation für alle Log-Zeilen
        user = interaction.user
        guild = interaction.guild

        # Manche Interactions schlagen ohne Guild fehl (DM)
        if guild is None:
            logger.error(f"[{corr_id}] Guild is None (vermutlich DM). Abbruch.")
            return

        logger.debug(
            f"[{corr_id}] on_submit START user={user}({user.id}) "
            f"guild={guild.name}({guild.id}) category_env='{TICKET_CATEGORY_NAME}'"
        )

        # (Optional) Falls es länger dauern könnte:
        # try:
        #     await interaction.response.defer(ephemeral=True, thinking=True)
        #     logger.debug(f"[{corr_id}] Interaction deferred (ephemeral).")
        # except Exception as e:
        #     logger.warning(f"[{corr_id}] Konnte nicht defern: {e.__class__.__name__}: {e}")

        # 1. Kategorie holen / erstellen
        try:
            category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
            logger.debug(
                f"[{corr_id}] Kategorie gesucht: {TICKET_CATEGORY_NAME} -> {category}"
            )
            if category is None:
                logger.debug(
                    f"[{corr_id}] Erstelle Kategorie '{TICKET_CATEGORY_NAME}' …"
                )
                category = await guild.create_category(
                    TICKET_CATEGORY_NAME, reason="Ticket System Setup (Modal Submit)"
                )
                logger.info(f"[{corr_id}] Kategorie erstellt id={category.id}")
        except Exception as e:
            logger.exception(f"[{corr_id}] Fehler bei Kategorie-Erstellung: {e}")
            # Versuche dem User wenigstens etwas zu sagen (falls noch nicht geantwortet)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Fehler beim Erstellen der Ticket-Kategorie.", ephemeral=True
                )
            return

        # 2. Channel-Namen bauen
        channel_name = f"ticket-{user.name}-{user.id}"
        # Channel-Namen auf <= 95 kürzen (Discord max 100)
        if len(channel_name) > 95:
            orig = channel_name
            channel_name = channel_name[:95]
            logger.debug(f"[{corr_id}] Channel-Name gekürzt: {orig} -> {channel_name}")

        logger.debug(f"[{corr_id}] Channel-Name vorbereitet: {channel_name}")

        # 3. Overwrites zusammenstellen
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                ),
            }
            admin_roles = []
            for role in guild.roles:
                try:
                    if role.permissions.administrator and role != guild.default_role:
                        overwrites[role] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True,
                        )
                        admin_roles.append(role.name)
                except Exception as e_role:
                    logger.warning(
                        f"[{corr_id}] Fehler beim Prüfen einer Rolle {role}: {e_role}"
                    )

            logger.debug(
                f"[{corr_id}] Overwrites fertig. Anzahl={len(overwrites)} "
                f"Admins={admin_roles}"
            )
        except Exception as e:
            logger.exception(f"[{corr_id}] Fehler beim Erstellen der Overwrites: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Fehler beim Erstellen der Rechte.", ephemeral=True
                )
            return

        # 4. Channel anlegen
        try:
            logger.debug(f"[{corr_id}] Erstelle Ticket-Channel …")
            ticket_ch = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Ticket von {user} | Anliegen-ID: {interaction.id}",
                reason="User erstellt Ticket über Modal",
            )
            logger.info(f"[{corr_id}] Ticket-Channel erstellt id={ticket_ch.id}")
        except discord.HTTPException as he:
            logger.exception(f"[{corr_id}] HTTPException beim Channel-Erstellen: {he}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Konnte den Ticket-Channel nicht erstellen.", ephemeral=True
                )
            return
        except Exception as e:
            logger.exception(f"[{corr_id}] Unerwarteter Fehler channel create: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Unerwarteter Fehler beim Channel-Erstellen.", ephemeral=True
                )
            return

        # 5. Erste Nachricht + Buttons
        try:
            embed = discord.Embed(
                title="🎫 Neues Ticket",
                description=(
                    f"**Ticket von {user.mention}**\n\n"
                    f"**Anliegen:**\n{self.anliegen.value}"
                ),
                color=discord.Color.green(),
            )
            view = CloseView(requester=user)
            logger.debug(f"[{corr_id}] Sende erste Embed-Nachricht …")
            first_msg = await ticket_ch.send(embed=embed, view=view)
            logger.info(f"[{corr_id}] Erste Nachricht gesendet id={first_msg.id}")
        except Exception as e:
            logger.exception(
                f"[{corr_id}] Fehler beim Senden der ersten Nachricht: {e}"
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Fehler beim Senden der Ticket-Nachricht.", ephemeral=True
                )
            return

        # 6. Persistieren
        try:
            logger.debug(f"[{corr_id}] Speichere Ticket in message_store …")
            message_store.add_ticket(guild.id, ticket_ch.id, first_msg.id)
            logger.debug(f"[{corr_id}] Speicherung abgeschlossen.")
        except Exception as e:
            logger.exception(f"[{corr_id}] Fehler beim Speichern im message_store: {e}")

        # 7. Bestätigungs-Nachricht im Ticket
        ok_msg = None
        try:
            logger.debug(f"[{corr_id}] Sende Bestätigung im Ticket-Channel …")
            ok_msg = await ticket_ch.send(
                f"{user.mention} ✅ Dein Ticket wurde erstellt. "
                "Ein Teammitglied meldet sich bald!"
            )
        except Exception as e:
            logger.exception(f"[{corr_id}] Fehler bei OK-Nachricht im Channel: {e}")

        # 8. Ephemeral Antwort an User
        try:
            if not interaction.response.is_done():
                logger.debug(f"[{corr_id}] Sende Ephemeral Response …")
                await interaction.response.send_message(
                    f"✅ Dein Ticket wurde erstellt: {ticket_ch.mention}",
                    ephemeral=True,
                )
            else:
                logger.debug(
                    f"[{corr_id}] Interaction response bereits abgeschlossen (deferred?)."
                )
        except Exception as e:
            logger.exception(f"[{corr_id}] Fehler bei der Ephemeral Antwort: {e}")

        # 9. OK-Nachricht nach 90s löschen
        async def _cleanup_confirmation():
            if ok_msg is None:
                return
            try:
                await asyncio.sleep(90)
                await ok_msg.delete()
                logger.debug(f"[{corr_id}] OK-Nachricht gelöscht.")
            except discord.NotFound:
                logger.debug(f"[{corr_id}] OK-Nachricht bereits weg.")
            except Exception as e:
                logger.exception(
                    f"[{corr_id}] Fehler beim Löschen der OK-Nachricht: {e}"
                )

        asyncio.create_task(_cleanup_confirmation())

        duration = time.perf_counter() - start_ts
        logger.debug(f"[{corr_id}] on_submit ENDE Dauer={duration:.3f}s")
