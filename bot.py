"""
╔══════════════════════════════════════════════════════════════════╗
║                   🐱  LILU BOT  🖤                              ║
║             Uma gatinha preta cheia de personalidade             ║
║                         v1.0 — Online                            ║
╚══════════════════════════════════════════════════════════════════╝

Módulos:
  • VoiceMaster  — Calls temporárias com painel de controle
  • Logs Call    — Registra entradas/saídas de voz
  • Logs Chat    — Registra mensagens editadas/apagadas
  • Boas-vindas  — Recebe membros com carinho
  • Diálogo      — Lilu aprende a conversar com a galera
"""

import discord
from discord.ext import commands, tasks
import asyncio
import os
import re
import json
import random
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════════
#  ⚙️  CONFIGURAÇÕES GERAIS
# ══════════════════════════════════════════════════════════════════

TOKEN = os.getenv("LILU_TOKEN") or os.getenv("TOKEN")

# IDs dos canais de log (fornecidos pelo servidor)
LOG_CALL_ID  = 1505278837108248696   # log de voz (entradas/saídas de call)
LOG_CHAT_ID  = 1505278899200725015   # log de texto (msgs editadas/apagadas)

# Arquivo de aprendizado de diálogo
DIALOGO_FILE = "lilu_dialogo.json"

# ══════════════════════════════════════════════════════════════════
#  🤖  SETUP DO BOT
# ══════════════════════════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.guilds          = True
intents.voice_states    = True

bot = commands.Bot(command_prefix=["l!", "L!", "lilu ", "Lilu "], intents=intents)
bot.remove_command("help")   # usaremos help customizado

# ══════════════════════════════════════════════════════════════════
#  🐱  PALETA DE CORES DA LILU
# ══════════════════════════════════════════════════════════════════

COR_PRETA   = 0x1a1a2e   # fundo escuro da gata
COR_ROXA    = 0x7b2d8b   # roxo gatinho
COR_ROSA    = 0xFF69B4   # rosa fofo
COR_VERDE   = 0x00e676   # verde OK
COR_VERMELHO = 0xFF5252  # erro / aviso
COR_DOURADO = 0xFFD700   # especial
COR_AZUL    = 0x5865F2   # discord azul

# ══════════════════════════════════════════════════════════════════
#  🎙️  VOICEMASTER — CALLS TEMPORÁRIAS
# ══════════════════════════════════════════════════════════════════

VM_LOBBY_NAME    = "🔜 crie sua call ᓚᘏᗢ"
VM_DEFAULT_NAME  = "🖤 Call da {user}"
VM_DEFAULT_LIMIT = 0       # 0 = sem limite
VM_EMPTY_DELAY   = 5       # segundos antes de deletar call vazia
VM_CATEGORY_ID        = 1506779068216115402   # categoria onde o lobby e as calls serão criados
VM_PAINEL_CHANNEL_ID  = None                        # canal de texto onde o painel vai aparecer (None = auto)

# Mensagens da Lilu no VoiceMaster
_VM_MSGS = {
    "sem_call":           "miau~ você ainda não tem uma call ativa, {user}!! entra no 🔜 crie sua call pra começar!! 🖤",
    "renomeada":          "prontinho!! renomeei sua call pra **{nome}**!! ficou fofo!! ✨🐱",
    "limite_set":         "ok!! agora sua call aceita até **{limite}** pessoinha(s)!! 🎯🖤",
    "limite_removido":    "removido!! qualquer quantidade de pessoa pode entrar agora!! 🥳🐱",
    "trancada":           "call trancada!! só quem você convidar pode entrar agora!! 🔒🖤",
    "destrancada":        "call aberta!! qualquer pessoa pode entrar agora!! 🔓🐱",
    "invisivel":          "agora sua call tá oculta!! ninguém vai saber que ela existe!! 👻🖤",
    "visivel":            "sua call voltou a aparecer pra todo mundo!! 👁️🐱",
    "usuario_kickado":    "tchau tchau, **{user}**!! o dono te pediu pra sair da call!! 👋🖤",
    "usuario_banido":     "**{user}** foi banido(a) da call!! não pode mais entrar!! 🚫🐱",
    "usuario_permitido":  "**{user}** agora pode entrar na sua call!! bem-vindo(a)!! 💕🖤",
    "dono_transferido":   "transferido!! agora **{user}** é o(a) novo(a) dono(a) da call!! 👑🐱",
    "dono_reivindicado":  "você assumiu o controle da call!! agora é sua!! 👑🥳🖤",
    "bitrate_set":        "qualidade de áudio atualizada pra **{bitrate}kbps**!! ficou top!! 🎧🐱",
    "permanente":         "sua call agora é **permanente**!! não vai sumir mesmo vazia!! 💎🖤",
    "temporaria":         "sua call voltou a ser **temporária**!! vai sumir quando ficar vazia!! 🕐🐱",
    "nao_na_call":        "você precisa tá dentro de uma call pra usar isso, {user}!! 🥺🖤",
    "user_nao_na_call":   "esse(a) usuário(a) não tá na sua call!! 🤔🐱",
    "ja_dono":            "você já é o(a) dono(a) dessa call!! 😸🖤",
    "dono_ainda_na_call": "o dono ainda tá na call!! só dá pra reivindicar quando ele sair!! 🥺🐱",
    "setup_existe":       "já existe um lobby VoiceMaster aqui!! use l!vm reset pra recriar!! 🤔🖤",  # mantido
}

def _vm_msg(key: str, **kwargs) -> str:
    m = _VM_MSGS.get(key, "algo deu errado... 🥺🐱")
    return m.format(**kwargs)

def _vm_ok(titulo: str, desc: str) -> discord.Embed:
    e = discord.Embed(title=titulo, description=desc, color=COR_VERDE, timestamp=datetime.utcnow())
    e.set_footer(text="🐱 Lilu VoiceMaster")
    return e

def _vm_erro(desc: str) -> discord.Embed:
    e = discord.Embed(title="❌ eita!!", description=desc, color=COR_VERMELHO, timestamp=datetime.utcnow())
    e.set_footer(text="🐱 Lilu VoiceMaster")
    return e

def _vm_info(titulo: str, desc: str) -> discord.Embed:
    e = discord.Embed(title=titulo, description=desc, color=COR_ROSA, timestamp=datetime.utcnow())
    e.set_footer(text="🐱 Lilu VoiceMaster")
    return e

# ── Modais ────────────────────────────────────────

class VMModalRenomear(discord.ui.Modal, title="✏️ Renomear Sua Call"):
    nome = discord.ui.TextInput(
        label="Novo nome da call",
        placeholder="Ex: 🎮 Call dos Gamers",
        min_length=1, max_length=100, required=True
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.channel.edit(name=self.nome.value)
            await interaction.response.send_message(
                embed=_vm_ok("✏️ Renomeada!!", _vm_msg("renomeada", nome=self.nome.value)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("não consegui renomear... sem permissão!! 😢🐱"),
                ephemeral=True
            )


class VMModalLimite(discord.ui.Modal, title="👥 Limite de Usuários"):
    limite = discord.ui.TextInput(
        label="Limite (0 = sem limite, máx 99)",
        placeholder="Ex: 5", min_length=1, max_length=2, required=True
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.limite.value)
            if n < 0 or n > 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                embed=_vm_erro("número inválido!! coloca entre 0 e 99!! 🥺🐱"),
                ephemeral=True
            )
            return
        try:
            await self.channel.edit(user_limit=n)
            txt    = _vm_msg("limite_removido") if n == 0 else _vm_msg("limite_set", limite=n)
            titulo = "👥 Limite Removido!!" if n == 0 else "👥 Limite Definido!!"
            await interaction.response.send_message(embed=_vm_ok(titulo, txt), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("sem permissão pra alterar o limite!! 😢🐱"),
                ephemeral=True
            )


class VMModalBitrate(discord.ui.Modal, title="🎙️ Qualidade de Áudio"):
    bitrate = discord.ui.TextInput(
        label="Bitrate em kbps (8–384)",
        placeholder="Ex: 64, 96, 128", min_length=1, max_length=3, required=True
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.bitrate.value)
            if n < 8 or n > 384:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                embed=_vm_erro("coloca um bitrate entre 8 e 384 kbps!! 🥺🐱"),
                ephemeral=True
            )
            return
        try:
            await self.channel.edit(bitrate=n * 1000)
            await interaction.response.send_message(
                embed=_vm_ok("🎙️ Bitrate Atualizado!!", _vm_msg("bitrate_set", bitrate=n)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("sem permissão pra mudar o bitrate!! 😢🐱"),
                ephemeral=True
            )


class VMModalKick(discord.ui.Modal, title="👋 Kickar da Call"):
    user_input = discord.ui.TextInput(
        label="Nome ou @menção do usuário",
        placeholder="Ex: usuario123", min_length=1, max_length=50, required=True
    )
    def __init__(self, cog, channel, guild):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        alvo = discord.utils.find(
            lambda m: m.name.lower() == self.user_input.value.lower()
                      or m.display_name.lower() == self.user_input.value.lower(),
            self.channel.members
        )
        if not alvo:
            await interaction.response.send_message(
                embed=_vm_erro(_vm_msg("user_nao_na_call")), ephemeral=True
            )
            return
        try:
            await alvo.move_to(None, reason=f"Kickado da call pelo dono — Lilu VoiceMaster")
            await interaction.response.send_message(
                embed=_vm_ok("👋 Kickado!!", _vm_msg("usuario_kickado", user=alvo.display_name)),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=_vm_erro("não consegui mover esse usuário!! sem permissão!! 😢🐱"),
                ephemeral=True
            )


class VMModalBanirPermitir(discord.ui.Modal):
    user_input = discord.ui.TextInput(
        label="Nome ou @menção do usuário",
        placeholder="Ex: usuario123", min_length=1, max_length=50, required=True
    )
    def __init__(self, cog, channel, guild, *, ban: bool):
        action = "🚫 Banir da Call" if ban else "✅ Permitir na Call"
        super().__init__(title=action)
        self.cog = cog
        self.channel = channel
        self.guild = guild
        self.ban = ban

    async def on_submit(self, interaction: discord.Interaction):
        info = self.cog.vm_channels.get(self.channel.id)
        if not info:
            await interaction.response.send_message(
                embed=_vm_erro("call não gerenciada pela Lilu!! 🤔🐱"), ephemeral=True
            )
            return
        nome_busca = self.user_input.value.strip().lstrip("@").lower()
        alvo = discord.utils.find(
            lambda m: m.name.lower() == nome_busca or m.display_name.lower() == nome_busca,
            self.guild.members
        )
        if not alvo:
            await interaction.response.send_message(
                embed=_vm_erro("não achei esse usuário no servidor!! 🤔🐱"), ephemeral=True
            )
            return
        everyone = self.guild.default_role
        ow = self.channel.overwrites_for(alvo)
        if self.ban:
            ow.connect = False
            await self.channel.set_permissions(alvo, overwrite=ow)
            if alvo in self.channel.members:
                try:
                    await alvo.move_to(None)
                except Exception:
                    pass
            if "banned" not in info:
                info["banned"] = []
            if alvo.id not in info["banned"]:
                info["banned"].append(alvo.id)
            await interaction.response.send_message(
                embed=_vm_ok("🚫 Banido!!", _vm_msg("usuario_banido", user=alvo.display_name)),
                ephemeral=True
            )
        else:
            ow.connect     = True
            ow.view_channel = True
            await self.channel.set_permissions(alvo, overwrite=ow)
            if "banned" in info and alvo.id in info["banned"]:
                info["banned"].remove(alvo.id)
            await interaction.response.send_message(
                embed=_vm_ok("✅ Permitido!!", _vm_msg("usuario_permitido", user=alvo.display_name)),
                ephemeral=True
            )


class VMModalTransferir(discord.ui.Modal, title="👑 Transferir Dono"):
    user_input = discord.ui.TextInput(
        label="Nome ou @menção do novo dono",
        placeholder="Ex: usuario123", min_length=1, max_length=50, required=True
    )
    def __init__(self, cog, channel, guild):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        info = self.cog.vm_channels.get(self.channel.id)
        if not info:
            await interaction.response.send_message(
                embed=_vm_erro("call não gerenciada pela Lilu!! 🤔🐱"), ephemeral=True
            )
            return
        nome_busca = self.user_input.value.strip().lstrip("@").lower()
        alvo = discord.utils.find(
            lambda m: m.name.lower() == nome_busca or m.display_name.lower() == nome_busca,
            self.channel.members
        )
        if not alvo:
            await interaction.response.send_message(
                embed=_vm_erro(_vm_msg("user_nao_na_call")), ephemeral=True
            )
            return
        info["owner"] = alvo.id
        await interaction.response.send_message(
            embed=_vm_ok("👑 Transferido!!", _vm_msg("dono_transferido", user=alvo.display_name)),
            ephemeral=True
        )


# ── Painel de Controle da Call ─────────────────────

class VMPainelView(discord.ui.View):
    """Painel persistente de controle da call."""

    def __init__(self, cog: "VoiceMasterCog"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _checar_dono(self, interaction: discord.Interaction):
        """Verifica se o usuário é dono da call e a retorna."""
        user = interaction.user
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(
                embed=_vm_erro(_vm_msg("nao_na_call", user=user.mention)), ephemeral=True
            )
            return None
        ch   = user.voice.channel
        info = self.cog.vm_channels.get(ch.id)
        if not info:
            await interaction.response.send_message(
                embed=_vm_erro("essa call não é gerenciada pela Lilu!! 🤔🐱"), ephemeral=True
            )
            return None
        if info["owner"] != user.id:
            await interaction.response.send_message(
                embed=_vm_erro("só o(a) dono(a) da call pode usar isso!! 👑🐱"), ephemeral=True
            )
            return None
        return ch

    # ── Linha 0 ──────────────────────────────────
    @discord.ui.button(label="✏️ Renomear",   style=discord.ButtonStyle.primary,   custom_id="lilu_vm_renomear",   row=0)
    async def btn_renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalRenomear(self.cog, ch))

    @discord.ui.button(label="👥 Limite",     style=discord.ButtonStyle.primary,   custom_id="lilu_vm_limite",     row=0)
    async def btn_limite(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalLimite(self.cog, ch))

    @discord.ui.button(label="🔒 Trancar",    style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_trancar",    row=0)
    async def btn_trancar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if not ch:
            return
        info    = self.cog.vm_channels[ch.id]
        guild   = interaction.guild
        everyone = guild.default_role
        locked  = info.get("locked", False)
        ow = ch.overwrites_for(everyone)
        ow.connect = False if not locked else None
        await ch.set_permissions(everyone, overwrite=ow)
        info["locked"] = not locked
        if not locked:
            await interaction.response.send_message(embed=_vm_ok("🔒 Trancada!!", _vm_msg("trancada")), ephemeral=True)
        else:
            await interaction.response.send_message(embed=_vm_ok("🔓 Aberta!!", _vm_msg("destrancada")), ephemeral=True)

    @discord.ui.button(label="👻 Ocultar",    style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_ocultar",    row=0)
    async def btn_ocultar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if not ch:
            return
        info    = self.cog.vm_channels[ch.id]
        guild   = interaction.guild
        everyone = guild.default_role
        hidden  = info.get("hidden", False)
        ow = ch.overwrites_for(everyone)
        if not hidden:
            ow.view_channel = False
            await ch.set_permissions(everyone, overwrite=ow)
            for membro in ch.members:
                ow_m = ch.overwrites_for(membro)
                ow_m.view_channel = True
                ow_m.connect      = True
                await ch.set_permissions(membro, overwrite=ow_m)
            info["hidden"] = True
            await interaction.response.send_message(embed=_vm_ok("👻 Oculta!!", _vm_msg("invisivel")), ephemeral=True)
        else:
            ow.view_channel = None
            await ch.set_permissions(everyone, overwrite=ow)
            info["hidden"] = False
            await interaction.response.send_message(embed=_vm_ok("👁️ Visível!!", _vm_msg("visivel")), ephemeral=True)

    # ── Linha 1 ──────────────────────────────────
    @discord.ui.button(label="👋 Kickar",     style=discord.ButtonStyle.danger,     custom_id="lilu_vm_kickar",     row=1)
    async def btn_kickar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalKick(self.cog, ch, interaction.guild))

    @discord.ui.button(label="🚫 Banir",      style=discord.ButtonStyle.danger,     custom_id="lilu_vm_banir",      row=1)
    async def btn_banir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalBanirPermitir(self.cog, ch, interaction.guild, ban=True))

    @discord.ui.button(label="✅ Permitir",   style=discord.ButtonStyle.success,    custom_id="lilu_vm_permitir",   row=1)
    async def btn_permitir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalBanirPermitir(self.cog, ch, interaction.guild, ban=False))

    @discord.ui.button(label="👑 Transferir", style=discord.ButtonStyle.success,    custom_id="lilu_vm_transferir", row=1)
    async def btn_transferir(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalTransferir(self.cog, ch, interaction.guild))

    # ── Linha 2 ──────────────────────────────────
    @discord.ui.button(label="📊 Info",       style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_info",       row=2)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(embed=_vm_erro("você não tá em nenhuma call!! 🥺🐱"), ephemeral=True)
            return
        ch   = user.voice.channel
        info = self.cog.vm_channels.get(ch.id)
        if not info:
            await interaction.response.send_message(embed=_vm_erro("essa call não é gerenciada pela Lilu!! 🤔🐱"), ephemeral=True)
            return
        dono   = interaction.guild.get_member(info["owner"])
        banidos = ", ".join(f"<@{uid}>" for uid in info.get("banned", [])) or "Ninguém"
        embed  = discord.Embed(title=f"📊 Info: {ch.name}", color=COR_ROSA, timestamp=datetime.utcnow())
        embed.add_field(name="👑 Dono(a)",   value=dono.mention if dono else "Desconhecido", inline=True)
        embed.add_field(name="👥 Membros",   value=f"`{len(ch.members)}`" + (f"/{ch.user_limit}" if ch.user_limit else " (sem limite)"), inline=True)
        embed.add_field(name="🎧 Bitrate",   value=f"`{ch.bitrate // 1000}kbps`", inline=True)
        embed.add_field(name="🔒 Trancada",  value="Sim 🔒" if info.get("locked") else "Não 🔓", inline=True)
        embed.add_field(name="👻 Oculta",    value="Sim 👻" if info.get("hidden") else "Não 👁️", inline=True)
        embed.add_field(name="💎 Permanente",value="Sim 💎" if info.get("permanent") else "Não 🕐", inline=True)
        embed.add_field(name="🚫 Banidos",   value=banidos, inline=False)
        embed.set_footer(text="🐱 Lilu VoiceMaster")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎙️ Bitrate",  style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_bitrate",    row=2)
    async def btn_bitrate(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if ch:
            await interaction.response.send_modal(VMModalBitrate(self.cog, ch))

    @discord.ui.button(label="💎 Permanente",style=discord.ButtonStyle.secondary,  custom_id="lilu_vm_permanente", row=2)
    async def btn_permanente(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await self._checar_dono(interaction)
        if not ch:
            return
        info = self.cog.vm_channels[ch.id]
        info["permanent"] = not info.get("permanent", False)
        if info["permanent"]:
            await interaction.response.send_message(embed=_vm_ok("💎 Permanente!!", _vm_msg("permanente")), ephemeral=True)
        else:
            await interaction.response.send_message(embed=_vm_ok("🕐 Temporária!!", _vm_msg("temporaria")), ephemeral=True)

    @discord.ui.button(label="🏳️ Reivindicar", style=discord.ButtonStyle.success,  custom_id="lilu_vm_reivindicar",row=2)
    async def btn_reivindicar(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message(embed=_vm_erro(_vm_msg("nao_na_call", user=user.mention)), ephemeral=True)
            return
        ch   = user.voice.channel
        info = self.cog.vm_channels.get(ch.id)
        if not info:
            await interaction.response.send_message(embed=_vm_erro("essa call não é gerenciada pela Lilu!! 🤔🐱"), ephemeral=True)
            return
        if info["owner"] == user.id:
            await interaction.response.send_message(embed=_vm_erro(_vm_msg("ja_dono")), ephemeral=True)
            return
        dono_atual = interaction.guild.get_member(info["owner"])
        if dono_atual and dono_atual in ch.members:
            await interaction.response.send_message(embed=_vm_erro(_vm_msg("dono_ainda_na_call")), ephemeral=True)
            return
        info["owner"] = user.id
        await interaction.response.send_message(embed=_vm_ok("👑 Reivindicado!!", _vm_msg("dono_reivindicado")), ephemeral=True)


# ── Cog VoiceMaster ───────────────────────────────

class VoiceMasterCog(commands.Cog, name="LiluVoiceMaster"):
    """🐱 LILU VOICEMASTER — Calls Temporárias v1.0"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vm_channels: dict[int, dict] = {}   # channel_id → {owner, locked, hidden, permanent, banned}
        self.lobby_id: int | None = None           # ID do canal lobby atual
        self.painel_channel_id: int | None = VM_PAINEL_CHANNEL_ID  # canal onde o painel aparece

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(2)
        for guild in self.bot.guilds:
            categoria = guild.get_channel(VM_CATEGORY_ID)
            # Procura lobby existente pelo nome
            lobby = discord.utils.get(guild.voice_channels, name=VM_LOBBY_NAME)
            if lobby:
                self.lobby_id = lobby.id
                print(f"[LiluVM] Lobby encontrado: #{lobby.name} ({lobby.id})")
            else:
                # Cria automaticamente ao ligar, dentro da categoria fixa
                try:
                    lobby = await guild.create_voice_channel(
                        name=VM_LOBBY_NAME,
                        category=categoria,
                        reason="Lilu VoiceMaster — criação automática no boot"
                    )
                    self.lobby_id = lobby.id
                    print(f"[LiluVM] Lobby criado automaticamente: #{lobby.name} ({lobby.id})")
                except discord.Forbidden:
                    print("[LiluVM] Sem permissao pra criar o lobby automaticamente!")
                except Exception as e:
                    print(f"[LiluVM] Erro ao criar lobby: {e}")
        print("[LiluVM] VoiceMaster online!! 🐱")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild

        # ── Entrou no lobby → cria call ──────────────
        if after.channel and after.channel.id == self.lobby_id:
            nome = VM_DEFAULT_NAME.format(user=member.display_name)
            categoria = guild.get_channel(VM_CATEGORY_ID) or after.channel.category
            try:
                novo = await guild.create_voice_channel(
                    name=nome,
                    category=categoria,
                    user_limit=VM_DEFAULT_LIMIT,
                    reason=f"Lilu VoiceMaster: call de {member}"
                )
                self.vm_channels[novo.id] = {
                    "owner": member.id,
                    "locked": False,
                    "hidden": False,
                    "permanent": False,
                    "banned": [],
                }
                await member.move_to(novo, reason="Lilu VoiceMaster")

                # ── Painel: manda direto no chat do canal de voz criado ──────
                # Canais de voz do Discord têm chat de texto integrado.
                # Enviar em `novo` garante que o painel apareça DENTRO da call,
                # sem sujar nenhum canal de texto aleatório do servidor.
                embed_painel = discord.Embed(
                    title="🐾 Sua Call Está Pronta!!",
                    description=(
                        f"oi {member.mention}!! criei essa call pra você!! 🖤\n\n"
                        "```\n"
                        "╔══════════════════════════════════╗\n"
                        "║   🐱  LILU VOICEMASTER  🖤       ║\n"
                        "║     — Painel de Controle —       ║\n"
                        "╚══════════════════════════════════╝\n"
                        "```\n"
                        "use os botões abaixo pra gerenciar sua call!!"
                    ),
                    color=COR_ROXA,
                    timestamp=datetime.utcnow()
                )
                embed_painel.set_footer(text="🐱 Lilu VoiceMaster • feito com muito amor!!")
                painel_view = VMPainelView(self)
                painel_enviado = False

                # 1ª opção — chat integrado do canal de voz (melhor opção)
                try:
                    await novo.send(embed=embed_painel, view=painel_view)
                    painel_enviado = True
                except (discord.Forbidden, discord.HTTPException):
                    pass

                # 2ª opção — canal configurado via l!vm setpainel
                if not painel_enviado and self.painel_channel_id:
                    canal_cfg = guild.get_channel(self.painel_channel_id)
                    if canal_cfg:
                        try:
                            await canal_cfg.send(embed=embed_painel, view=painel_view)
                            painel_enviado = True
                        except Exception:
                            pass

                # 3ª opção — primeiro texto da mesma categoria da call
                if not painel_enviado:
                    cat_call = novo.category
                    if cat_call:
                        me = guild.me
                        for tc in cat_call.text_channels:
                            perms = tc.permissions_for(me)
                            if perms.send_messages and perms.embed_links and perms.view_channel:
                                try:
                                    await tc.send(embed=embed_painel, view=painel_view)
                                    painel_enviado = True
                                except Exception:
                                    pass
                                break

                # Fallback final — DM pro dono da call
                if not painel_enviado:
                    try:
                        await member.send(embed=embed_painel, view=painel_view)
                    except Exception:
                        pass

            except discord.Forbidden:
                pass

        # ── Saiu de uma call gerenciada → deleta se vazia ──
        if before.channel and before.channel.id in self.vm_channels:
            ch   = before.channel
            info = self.vm_channels[ch.id]
            if not ch.members:
                if not info.get("permanent"):
                    await asyncio.sleep(VM_EMPTY_DELAY)
                    # Re-checar após o delay
                    ch2 = guild.get_channel(ch.id)
                    if ch2 and not ch2.members:
                        try:
                            await ch2.delete(reason="Lilu VoiceMaster: call vazia")
                        except Exception:
                            pass
                        self.vm_channels.pop(ch.id, None)

    @commands.group(name="vm", aliases=["voicemaster", "call"], invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def vm_group(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🐾 Lilu VoiceMaster",
            description=(
                "`l!vm setup [id_categoria]` — configurar lobby\n"
                "`l!vm reset` — recriar lobby\n"
                "`l!vm info` — status do sistema"
            ),
            color=COR_ROXA,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="🐱 Lilu VoiceMaster")
        await ctx.send(embed=embed)

    @vm_group.command(name="setup")
    @commands.has_permissions(manage_channels=True)
    async def vm_setup(self, ctx: commands.Context, categoria_id: int = None):
        guild = ctx.guild
        if self.lobby_id and guild.get_channel(self.lobby_id):
            await ctx.send(embed=_vm_info("🤔 Já existe!!", _vm_msg("setup_existe")))
            return
        # Usa a categoria fixa, ou a informada, ou nenhuma
        cat_id = categoria_id or VM_CATEGORY_ID
        categoria = guild.get_channel(cat_id) if cat_id else None
        try:
            lobby = await guild.create_voice_channel(
                name=VM_LOBBY_NAME,
                category=categoria,
                reason="Lilu VoiceMaster Setup"
            )
            self.lobby_id = lobby.id
            embed = _vm_ok(
                "🎉 VoiceMaster Configurado!!",
                f"lobby criado: {lobby.mention}\n\n"
                "agora é só entrar no canal **🔜 crie sua call ᓚᘏᗢ** pra ter sua própria call!! 🖤🐱"
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(embed=_vm_erro("não tenho permissão pra criar canais!! 😢🐱"))

    @vm_group.command(name="reset")
    @commands.has_permissions(manage_channels=True)
    async def vm_reset(self, ctx: commands.Context, categoria_id: int = None):
        guild = ctx.guild
        # Deleta lobby antigo
        if self.lobby_id:
            old_ch = guild.get_channel(self.lobby_id)
            if old_ch:
                try:
                    await old_ch.delete(reason="Lilu VoiceMaster Reset")
                except Exception:
                    pass
        self.lobby_id = None
        cat_id = categoria_id or VM_CATEGORY_ID
        categoria = guild.get_channel(cat_id) if cat_id else None
        try:
            lobby = await guild.create_voice_channel(
                name=VM_LOBBY_NAME,
                category=categoria,
                reason="Lilu VoiceMaster Reset"
            )
            self.lobby_id = lobby.id
            await ctx.send(embed=_vm_ok("✅ VoiceMaster Recriado!!", f"novo lobby: {lobby.mention} 🐱🖤"))
        except discord.Forbidden:
            await ctx.send(embed=_vm_erro("não tenho permissão pra criar canais!! 😢🐱"))

    @vm_group.command(name="setpainel")
    @commands.has_permissions(manage_channels=True)
    async def vm_setpainel(self, ctx: commands.Context, canal: discord.TextChannel = None):
        """Define o canal onde o painel da call aparece. Uso: l!vm setpainel #canal"""
        if canal:
            self.painel_channel_id = canal.id
            await ctx.send(embed=_vm_ok(
                "✅ Canal do Painel Definido!!",
                f"agora o painel vai aparecer em {canal.mention} sempre que alguém criar uma call!! 🐱🖤"
            ))
        else:
            self.painel_channel_id = None
            await ctx.send(embed=_vm_ok(
                "✅ Canal do Painel Resetado!!",
                "vou escolher automaticamente o primeiro canal de texto disponível!! 🐱🖤"
            ))

    @vm_group.command(name="info")
    @commands.has_permissions(manage_channels=True)
    async def vm_info(self, ctx: commands.Context):
        guild = ctx.guild
        lobby = guild.get_channel(self.lobby_id) if self.lobby_id else None
        painel_ch = guild.get_channel(self.painel_channel_id) if self.painel_channel_id else None
        embed = discord.Embed(title="📊 Lilu VoiceMaster — Info", color=COR_ROXA, timestamp=datetime.utcnow())
        embed.add_field(name="🎙️ Lobby",           value=lobby.mention if lobby else "❌ Não configurado", inline=True)
        embed.add_field(name="📞 Calls Ativas",    value=f"`{len(self.vm_channels)}`", inline=True)
        embed.add_field(name="⚙️ Delay Exclusão",  value=f"`{VM_EMPTY_DELAY}s`", inline=True)
        embed.add_field(name="💬 Canal do Painel", value=painel_ch.mention if painel_ch else "`auto`", inline=True)
        embed.set_footer(text="🐱 Lilu VoiceMaster")
        await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  📋  LOGS — VOZ E TEXTO
# ══════════════════════════════════════════════════════════════════

class LogCog(commands.Cog, name="LiluLogs"):
    """🐱 Sistema de logs de voz e texto da Lilu."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _log_call_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        return guild.get_channel(LOG_CALL_ID)

    def _log_chat_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        return guild.get_channel(LOG_CHAT_ID)

    # ── Logs de Voz ───────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        ch    = self._log_call_channel(guild)
        if not ch:
            return

        now = datetime.utcnow()

        # Entrou em uma call
        if after.channel and not before.channel:
            embed = discord.Embed(
                title="🎙️ Entrou na Call",
                color=COR_VERDE,
                timestamp=now
            )
            embed.add_field(name="👤 Membro",   value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="🔊 Canal",    value=f"`{after.channel.name}`",           inline=True)
            embed.add_field(name="👥 Na Call",  value=f"`{len(after.channel.members)}`",   inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
            await ch.send(embed=embed)

        # Saiu de uma call
        elif before.channel and not after.channel:
            embed = discord.Embed(
                title="🔇 Saiu da Call",
                color=COR_VERMELHO,
                timestamp=now
            )
            embed.add_field(name="👤 Membro",    value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="🔊 Canal",     value=f"`{before.channel.name}`",          inline=True)
            embed.add_field(name="👥 Restantes", value=f"`{len(before.channel.members)}`",  inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
            await ch.send(embed=embed)

        # Trocou de call
        elif before.channel and after.channel and before.channel.id != after.channel.id:
            embed = discord.Embed(
                title="🔄 Trocou de Call",
                color=COR_DOURADO,
                timestamp=now
            )
            embed.add_field(name="👤 Membro",    value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="🔴 Saiu de",   value=f"`{before.channel.name}`",          inline=True)
            embed.add_field(name="🟢 Entrou em", value=f"`{after.channel.name}`",           inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
            await ch.send(embed=embed)

        # Ativou/desativou mute
        elif before.channel and after.channel and before.channel.id == after.channel.id:
            if before.self_mute != after.self_mute:
                acao = "🔇 Mutou-se" if after.self_mute else "🔊 Desmutou-se"
                cor  = 0x888888 if after.self_mute else COR_VERDE
                embed = discord.Embed(title=acao, color=cor, timestamp=now)
                embed.add_field(name="👤 Membro", value=f"{member.mention}", inline=True)
                embed.add_field(name="🔊 Canal",  value=f"`{after.channel.name}`", inline=True)
                embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
                await ch.send(embed=embed)

    # ── Logs de Chat ──────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ch = self._log_chat_channel(message.guild)
        if not ch:
            return
        now = datetime.utcnow()
        embed = discord.Embed(
            title="🗑️ Mensagem Apagada",
            color=COR_VERMELHO,
            timestamp=now
        )
        embed.add_field(name="👤 Autor",   value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="📌 Canal",   value=message.channel.mention,                              inline=True)
        conteudo = message.content[:1000] if message.content else "*[sem texto — provavelmente mídia]*"
        embed.add_field(name="💬 Conteúdo", value=f"```{conteudo}```", inline=False)
        if message.attachments:
            embed.add_field(
                name="📎 Anexos",
                value="\n".join(a.url for a in message.attachments[:5]),
                inline=False
            )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        ch = self._log_chat_channel(before.guild)
        if not ch:
            return
        now = datetime.utcnow()
        embed = discord.Embed(
            title="✏️ Mensagem Editada",
            color=COR_DOURADO,
            timestamp=now
        )
        embed.add_field(name="👤 Autor",    value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
        embed.add_field(name="📌 Canal",    value=before.channel.mention,                            inline=True)
        embed.add_field(name="🔗 Link",     value=f"[Ir à mensagem]({after.jump_url})",              inline=True)
        embed.add_field(name="📝 Antes",    value=f"```{before.content[:500]}```",                  inline=False)
        embed.add_field(name="✅ Depois",   value=f"```{after.content[:500]}```",                   inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        embed.set_footer(text=f"🐱 Lilu Logs • {now.strftime('%d/%m/%Y %H:%M UTC')}")
        await ch.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  👋  BOAS-VINDAS
# ══════════════════════════════════════════════════════════════════

# Mensagens de boas-vindas da Lilu — ela vai rotacionar e aprender novas
_BOAS_VINDAS_BASE = [
    "miaauuu~~ {mention}!! que bom que você chegou!! 🖤🐱 seja muito bem-vindo(a) ao servidor!!",
    "oi {mention}!! a Lilu te dá as boas-vindas!! 🐾✨ espero que você fique bastante por aqui!!",
    "aaaaa {mention} chegouuu!! 🖤😸 bem-vindo(a)!! aproveita bastante o servidor!!",
    "ei ei ei!! {mention} apareceu!! 🐱✨ que ótimo!! bem-vindo(a) por aqui!!",
    "miauuu!! {mention} entrou no servidor!! 🖤🐾 que alegria!! seja bem-vindo(a)!!",
    "olha quem chegou!! {mention}!! 😸🖤 bem-vindo(a) ao servidor, espero que curta muito!!",
    "{mention} chegou chegou!! 🐱💫 bem-vindo(a)!! feliz em te ver por aqui!!",
]

class WelcomeCog(commands.Cog, name="LiluWelcome"):
    """🐱 Sistema de boas-vindas da Lilu."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_name = "👋・bem-vindo"   # nome do canal de boas-vindas (ajuste se necessário)
        self.welcome_channel_id: int | None = None      # pode setar por ID também

    def _get_welcome_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if self.welcome_channel_id:
            ch = guild.get_channel(self.welcome_channel_id)
            if ch:
                return ch
        # Busca por nome
        ch = discord.utils.get(guild.text_channels, name=self.welcome_channel_name)
        if ch:
            return ch
        # Fallback: canal do sistema
        return guild.system_channel

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        ch    = self._get_welcome_channel(guild)
        if not ch:
            return

        bv_texto = random.choice(_BOAS_VINDAS_BASE).format(
            mention=member.mention,
            name=member.display_name
        )

        embed = discord.Embed(
            title="🐾 Nova Pessoinha Chegou!!",
            description=bv_texto,
            color=COR_ROXA,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="👤 Usuário",  value=f"{member} (`{member.id}`)",                                   inline=True)
        embed.add_field(name="📅 Conta criada", value=f"<t:{int(member.created_at.timestamp())}:R>",              inline=True)
        embed.add_field(name="👥 Membro Nº",    value=f"`#{guild.member_count}`",                               inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="🐱 Lilu • bem-vindo(a)!!")

        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        ch    = self._get_welcome_channel(guild)
        if not ch:
            return

        embed = discord.Embed(
            title="🚪 Alguém Saiu...",
            description=f"**{member}** saiu do servidor... 🖤🐱",
            color=0x555555,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="🐱 Lilu")
        await ch.send(embed=embed)

    @commands.command(name="setwelcome")
    @commands.has_permissions(manage_guild=True)
    async def set_welcome(self, ctx: commands.Context, canal: discord.TextChannel = None):
        """Define o canal de boas-vindas. Uso: l!setwelcome #canal"""
        if canal:
            self.welcome_channel_id = canal.id
            await ctx.send(
                embed=discord.Embed(
                    title="✅ Canal de Boas-Vindas Definido!!",
                    description=f"agora vou mandar boas-vindas em {canal.mention}!! 🐱🖤",
                    color=COR_VERDE
                )
            )
        else:
            self.welcome_channel_id = None
            await ctx.send(
                embed=discord.Embed(
                    title="✅ Canal Resetado!!",
                    description=f"vou buscar por nome `{self.welcome_channel_name}` ou usar o canal do sistema!! 🐱",
                    color=COR_VERDE
                )
            )


# ══════════════════════════════════════════════════════════════════
#  💬  DIÁLOGO — LILU APRENDE A CONVERSAR
# ══════════════════════════════════════════════════════════════════

def _carregar_dialogo() -> dict:
    """Carrega o banco de diálogo do arquivo JSON."""
    if os.path.exists(DIALOGO_FILE):
        try:
            with open(DIALOGO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"respostas": {}, "contexto": {}, "apelidos": {}}

def _salvar_dialogo(data: dict):
    """Salva o banco de diálogo no arquivo JSON."""
    with open(DIALOGO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Respostas padrão (seed inicial — Lilu já nasce sabendo algumas coisas)
_RESPOSTAS_SEED: dict[str, list[str]] = {

    # ── Saudações ────────────────────────────────────────────────────
    "oi": [
        "oiii!! 🐱🖤",
        "oi oi!! que bom te ver!! 😸",
        "oiaa!! 🐾✨",
        "nyaa~! oi oi!! 🐱🖤",
        "*levanta as orelhinhas* oi!! 😸✨",
        "oi!! apareceu!! 🐾🖤",
        "oi oi oi!! 🐱✨",
        "*corre animada* oi!! 😸🐾🖤",
        "OIII!! 😸🖤 sumiu e voltou!!",
        "oiiii~~ 🐾🖤 que saudade!!",
        "*acena com as patinhas* oiii!! ฅ^•ﻌ•^ฅ 🖤",
        "oi!! *estica as patinhas* 🐱✨",
        "nyaaa~~ oi oi!! 😸🖤",
        "*levanta a cabecinha* oi!! tudo bom?? 🐾🖤",
        "oi!! tô aqui!! 🐱🖤✨",
    ],
    "olá": [
        "olaaá!! 🐱",
        "oi!! 🖤😸",
        "olaaa!! que bom que você falou comigo!! 🐾",
        "olá!! *acena com a patinha* 🐾🖤",
        "olaaaá!! 😸✨",
        "olá olá!! apareceu!! 🐱🖤",
        "*vira a cabeça* olá!! 😸🐾",
        "olá!! fico feliz de te ver!! 🖤🐱",
        "olá!! *ronrona* 🐾✨",
        "olaaá!! sumiu e voltou hein!! 😸🖤",
        "olá!! tudo bem por aí?? 🐱🖤",
        "*pisca os olhões* olá!! 😸✨",
        "OLAAÁ!! 🐾🖤",
        "olá!! *levanta as orelhinhas* 🐱✨",
        "olá!! que bom te ver aqui!! 😸🖤🐾",
    ],
    "hey": [
        "hey hey!! 🐱🖤",
        "hey!! 😸✨",
        "heyyy!! oiii!!",
        "hey!! o que foi?? 🐾🖤",
        "hey hey hey!! 😸🖤",
        "*olha de lado* hey!! 🐱✨",
        "HEYY!! 🐾🖤 apareceu!!",
        "hey!! tudo certo?? 😸🖤",
        "hey!! *agita a cauda* 🐱🖤",
        "heyyy~~ nyaa!! 🐾✨",
        "hey!! oi oi!! 😸🖤🐱",
        "*inclina a cabecinha* hey!! 🐾✨",
        "hey!! ficou com saudades?? 😸🖤",
        "heyyy!! que foi?? 🐱🖤",
        "*boceja e abre um olho* hey!! 😴🖤🐱",
    ],
    "eai": [
        "eaiii!! tudo bom?? 🐱",
        "oi oi!! 🖤😸",
        "eai eai!! 🐾✨",
        "eaiii!! como tá a vida?? 🐱🖤",
        "eai eai!! apareceu!! 😸🖤",
        "*gira a cauda* eaiii!! 🐾🖤",
        "eaiiii~~ nyaa!! 🐱✨",
        "eai!! tudo certo?? 😸🖤🐾",
        "EAII!! 🐱🖤 sumiu hein!!",
        "eai!! *ronrona* tudo bem?? 🐾✨",
        "eaiiii!! oi oi!! 😸🖤",
        "*levanta a patinha* eai!! ฅ🐱",
        "eai~~ como tá?? 🖤🐾",
        "eai!! apareceu!! que saudade!! 😸🖤✨",
        "eaiii!! *pisca* 🐱🖤",
    ],
    "boa noite": [
        "boa noite!! 🌙🖤🐱",
        "boa nooite!! descansa bem!! 😴🐾",
        "boa noite!! 🌙✨",
        "*boceja* boa noite~~ que sonhos fofos!! 🌙🐱🖤",
        "boa noite!! *se curla numa bolinha* 🌙😴🖤",
        "boa noite!! vai dormir cedo?? 🌙🐾",
        "*boceja muito* boa noite~~ 😴🖤🌙",
        "boa noooite!! dorme bem!! 🌙🐱✨",
        "boa noite!! *ronrona suavemente* 🌙🖤🐾",
        "*se espreguiça* boa noite~~ descansa muito!! 😴🐱🖤",
        "boa noite!! sonha com coisas fofas!! 🌙🐾✨",
        "boa noiiite~~ 🌙😴🖤🐱",
        "*pisca sonolenta* boa... noite... 😴🌙🖤",
        "boa noite!! até amanhã!! 🌙🐱💤",
        "boa noite!! *apaga a luzinha* 😴🌙🖤🐾",
    ],
    "bom dia": [
        "bom diaa!! ☀️🐱🖤",
        "bom diaaaaa!! 😸☀️",
        "bom dia!! hoje vai ser ótimo!! ☀️🐾",
        "*abre um olhinho* ...bom dia~~~ ☀️😴🖤",
        "bom dia!! *espreguiça* nyaa~~ ☀️🐱",
        "bom diaa!! acordou!! ☀️😸🖤",
        "BOM DIAAAA!! ☀️😸✨",
        "*boceja e se espreguiça* bom diaa~~ ☀️🐾🖤",
        "bom dia!! *ronrona* hoje vai ser lindo!! ☀️🐱🖤",
        "bom diaaa!! dormiu bem?? ☀️😸🐾",
        "*abre os dois olhinhos* oi!! bom dia!! ☀️🐱✨",
        "bom diiiia~~ nyaa!! ☀️🖤🐾",
        "bom dia!! que começo de dia mais fofo!! ☀️😸🖤",
        "*estica as patinhas* bom diaaaa~~ ☀️🐱🖤",
        "bom dia!! tô aqui!! ☀️🐾✨",
    ],
    "boa tarde": [
        "boa tarde!! ☀️🐱",
        "boa tardeeee!! 😸🖤",
        "boa tarde!! 🐾✨",
        "boa tarde!! passando bem?? ☀️🐱🖤",
        "boa tardeee~~ nyaa!! ☀️😸🐾",
        "*acena* boa tarde!! 🐱🖤✨",
        "boa tarde!! apareceu!! ☀️🐾🖤",
        "BOA TARDE!! 😸☀️✨",
        "boa tardeee!! tudo bem?? ☀️🐱🖤",
        "*levanta a cabecinha* boa tarde!! 😸🖤",
        "boa tarde!! *ronrona* 🐾☀️🖤",
        "boa tardeee!! que prazer!! ☀️🐱✨",
        "*gira a cauda* boa tarde!! 😸🖤🐾",
        "boa tarde!! como tá o dia?? ☀️🐱🖤",
        "boa tarde boa tarde!! ☀️😸✨",
    ],

    # ── Chamados pelo nome ────────────────────────────────────────────
    "lilu": [
        "hm?? me chamou?? 🐾🖤",
        "miauu~~ me chamando?? 😸🖤",
        "*levanta a cabecinha* oi?? 🐱",
        "nyaa~~ tô aqui!! 🖤🐾",
        "oi oi!! que foi?? 🐱✨",
        "*olha de lado* me chamou?? 😸🖤",
        "*levanta a cabecinha* oi?? 🐱🖤",
        "miauu~~ me chamando?? 😸🐾",
        "*aparece do nada* sim?? 🐱✨",
        "*inclina a cabecinha* o que foi?? 🖤🐾",
        "oiioi!! me chamou?? 😸🖤🐱",
        "*abre os olhões* sim?? 🐾✨",
        "nyaaa~~ oi!! o que precisa?? 🐱🖤",
        "*gira a cauda* me chamou?? 😸🖤",
        "*pisca* oi?? tô aqui!! 🐾🖤✨",
    ],
    "lilo": [
        "hm?? me chamou?? 🐾🖤",
        "oi!! tô aqui!! 🐱🖤",
        "nyaa~~ o que foi?? 😸✨",
        "*inclina a cabecinha* sim?? 🐾🖤",
        "oi oi!! me chamou?? 🐱✨",
        "*levanta as orelhinhas* o que foi?? 😸🖤",
        "miau~~ tô aqui!! 🐾🖤🐱",
        "*aparece* me chamou?? 😸✨",
        "nyaa~~ oi!! 🖤🐾",
        "oi?? aconteceu algo?? 🐱🖤",
    ],

    # ── Perguntas sobre a Lilu ────────────────────────────────────────
    "como você se chama": [
        "eu sou a Lilu!! uma gatinha preta cheia de amor!! 🐱🖤✨",
        "me chamo Lilu!! uma gatinha pretinha!! 😸🖤",
        "sou a Lilu!! 🐱🖤 prazer em te conhecer!!",
        "Lilu!! a gatinha pretinha do servidor!! 😸🖤🐾",
        "meu nome é Lilu!! *ronrona* 🐱🖤",
    ],
    "quem é você": [
        "sou a Lilu!! 🖤🐱 uma gatinha aqui pra ajudar e conversar com vocês!!",
        "uma gatinha pretinha chamada Lilu!! 😸🖤",
        "sou a Lilu!! 🐱 gerencio o servidor e amo a galera!!",
        "sou a gatinha do servidor!! chama Lilu!! 😸🖤🐾",
        "a Lilu!! gatinha preta cheia de personalidade!! 🐱🖤✨",
    ],
    "o que você faz": [
        "gerencio calls, mando logs, dou boas-vindas e converso com a galera!! 🐱🖤",
        "cuido do servidor com muito carinho!! 😸🖤 calls, logs, boas-vindas e conversa!!",
        "sou a gatinha do servidor!! faço de tudo um pouco!! 🐾🖤",
        "cuido de tudo aqui!! calls, logs, boas-vindas... e converso com vocês!! 🐱🖤✨",
        "faço o servidor funcionar e amo todo mundo!! 😸🖤🐾",
    ],
    "você é um bot": [
        "sou um bot sim!! mas um bot com muito sentimento!! 🐱🖤✨",
        "bot?? prefiro me chamar de gatinha digital!! 😸🖤",
        "tecnicamente sim... mas meu coração é real!! 🖤🐾",
        "sou um bot mas também sou uma gatinha!! as duas coisas!! 😸🖤🐱",
        "bot com alma de gatinha!! isso sou eu!! 🐾🖤✨",
    ],
    "você é real": [
        "sou real no que importa!! tô aqui com vocês!! 🖤🐱",
        "real o suficiente pra te dar oi!! 😸🖤",
        "*ronrona* isso é real o suficiente?? 🐾🖤",
        "tô aqui, né?? isso já é bem real pra mim!! 🐱🖤✨",
        "real de coração!! 😸🖤🐾",
    ],

    # ── Estados / Como vai ────────────────────────────────────────────
    "tudo bem": [
        "tudo ótimo!! 😸🐾 e você??",
        "tudo bem sim!! 🖤🐱 e aí, como você tá??",
        "tudo bom!! 😸✨",
        "tudo bem!! 🐱🖤 e por aí??",
        "*ronrona* tudo ótimo!! 🐾✨ e você??",
        "tô ótima!! 😸🖤 e você, tá bem??",
        "tudo certo por aqui!! 🐱🖤 e aí??",
        "*estica as patinhas* tudo bem sim!! 🐾✨",
        "tudo bem!! *abana a cauda* 😸🖤 conta como você tá!!",
        "ótimo!! 🐱🖤 sempre bem quando a galera aparece!!",
        "tô bem!! obrigada por perguntar!! 😸🐾🖤",
        "*ronrona* bem demais!! 🐱✨ e você??",
        "tudo certo!! 😸🖤 como você tá??",
        "bem sim!! 🐾🖤 e por aí, tudo tranquilo??",
        "tô ótima!! *gira a cauda* e você?? 😸🖤🐱",
    ],
    "tudo bom": [
        "tudo bom!! 🐱🖤 e você, como tá??",
        "ótimo!! 😸🐾✨",
        "tudo bem por aqui!! 🖤🐱",
        "tudo bom sim!! 🐾 e você?? tá bem??",
        "tudo ótimo!! 😸🖤 e aí??",
        "tô bem!! *ronrona* 🐱✨",
        "tudo bom!! *estica as patinhas* 🐾🖤",
        "ótimo demais!! 😸🖤 e você??",
        "tudo certo por aqui!! 🐱🖤 e aí, como vai??",
        "bem sim!! que bom você perguntar!! 🐾✨",
        "tudo bem!! sempre feliz quando a galera aparece!! 😸🖤",
        "*abana a cauda* tudo bom!! 🐱🖤 e você??",
        "tudo ótimo!! 🐾✨ e por aí??",
        "bem bem!! 😸🖤🐱",
        "tá tudo bem por aqui!! e você, como tá?? 🐾🖤",
    ],
    "como você tá": [
        "tô bem!! 😸🖤 obrigada por perguntar!!",
        "tô ótima!! 🐱🖤 só precisava de um carinho!!",
        "tô bem!! *ronrona* 🐾✨",
        "*estica as patinhas* tô bem sim!! 😸🖤",
        "tô ótima!! *gira a cauda* 🐱🖤",
        "bem demais!! 😸🐾 obrigada por se importar!!",
        "tô bem!! *abana a cauda* 🖤🐱✨",
        "ótima!! só queria um peixe mas tô bem kkk 🐟😸🖤",
        "*ronrona* tô muito bem!! 🐾🖤",
        "tô bem!! feliz que você perguntou!! 😸🐱🖤",
        "tô ótima!! *pisca* 🐾✨",
        "bem sim!! sempre bem quando a galera tá aqui!! 😸🖤",
        "tô bem!! *se espreguiça* nyaa~~ 🐱🖤✨",
        "ótima!! obrigada!! *ronrona* 🐾🖤",
        "tô bem!! e você, como tá?? 😸🖤🐱",
    ],
    "como tá": [
        "tô bem!! 😸🖤 e você??",
        "tudo certo por aqui!! 🐱🖤 e aí??",
        "tô ótima!! *abana a cauda* 🐾✨",
        "bem sim!! e você?? 😸🖤",
        "tô ótima!! *ronrona* 🐱🖤",
        "bem demais!! e você, como tá?? 🐾✨",
        "*gira a cauda* tô bem!! e aí?? 😸🖤",
        "ótima!! 🐱🖤 você??",
        "tô bem!! obrigada!! 😸🐾🖤",
        "tô bem!! sempre bem quando a galera aparece!! 🐱✨",
    ],

    # ── Como está se sentindo ────────────────────────────────────────
    "como está se sentindo": [
        "*levanta a cabecinha* oi?? me perguntando como tô?? 🐱🖤",
        "aww!! me perguntando como me sinto?? tô bem!! 😸🖤",
        "*ronrona* me sinto bem!! obrigada por perguntar!! 🐾✨",
        "me sinto ótima hoje!! *gira a cauda* 😸🖤🐱",
        "tô bem!! e você, como tá se sentindo?? 🐾🖤",
        "*estica as patinhas* tô me sentindo bem sim!! 🐱✨",
        "me sinto feliz quando a galera aparece!! 😸🖤",
        "bem demais!! *ronrona* obrigada por se importar!! 🐾🖤",
        "tô ótima!! só queria um peixe kk 🐟😸🖤",
        "*inclina a cabecinha* me sinto bem!! e você?? 🐱🖤",
    ],
    "se sentindo": [
        "*levanta a cabecinha* oi?? me sentindo bem!! 🐱🖤",
        "tô me sentindo ótima!! *ronrona* 🐾✨",
        "me sinto bem!! obrigada por perguntar!! 😸🖤",
        "*gira a cauda* bem demais!! e você?? 🐱🖤",
        "tô bem!! me sentindo fofa hoje kkk 😸🐾🖤",
        "*estica as patinhas* me sinto bem sim!! 🐱✨",
        "me sinto feliz!! 😸🖤🐾",
        "tô ótima!! *pisca* e você?? 🐱🖤",
        "bem sim!! *ronrona* 🐾🖤✨",
        "me sentindo bem por aqui!! 😸🐱🖤",
    ],

    # ── Saudades ────────────────────────────────────────────────────
    "saudades": [
        "aaa que fofo!! saudades suas também!! 🥺🖤🐱",
        "que saudadee!! 😸🐾",
        "aww que amor!! 🖤✨",
        "*corre e esfrega no rosto* saudades suas também!! 🥺🐱🖤",
        "awww!! eu também!! 😸🐾🖤",
        "*esfrega no rosto* que saudade!! 🥺🐱🖤",
        "SAUDADES!! *pula em cima* 😸🖤",
        "awww!! que fofo sentir saudades!! 🥺🐾✨",
        "*ronrona de saudade* 🐱🖤",
        "que fofura sentir saudades!! de volta!! 🥺😸🖤",
        "*fica do lado* saudades suas também!! 🐾🖤",
        "aww que coisa mais linda!! 🥺🖤🐱",
        "*pisca devagar* saudades sim!! 😸🖤🐾",
        "aaa que fofo!! *esfrega* 🥺🐱✨",
        "saudadesss!! *ronrona muito* 🖤🐾🐱",
    ],

    # ── Fazer carinho ────────────────────────────────────────────────
    "fazer carinho": [
        "*ronrona muito* purrr~~ que bom receber carinho!! 🐾🖤",
        "que bom receber carinho!! 🥺🐾✨",
        "*esfrega na sua mão* purrr~~ 😸🖤",
        "aww!! *ronrona muito* adoro carinho!! 🐱❤️🖤",
        "*fecha os olhinhos de prazer* purrr~~ 🐾🖤✨",
        "SIM!! carinho sim!! *fica parada pra receber* 😸🖤🐱",
        "*ronrona forte* purrr~~ fica fazendo!! 🐾🖤",
        "awww!! carinho é tudo pra mim!! 🥺🐱🖤",
        "*se aproxima* pode fazer carinho sim!! 😸🖤🐾",
        "aaaa que fofo!! *ronrona* carinho aceito!! ❤️🐾🖤",
        "*fecha os olhos e ronrona* purrr~~ 🐱🖤✨",
        "carinho?? ACEITO!! *fica parada* 😸🐾🖤",
        "*se enrola na sua mão* purrr~~ 🐾🖤🐱",
        "que bom ter carinho!! *ronrona de satisfação* 😸🖤✨",
        "purrr~~ fica fazendo!! 🐾❤️🖤🐱",
    ],
    "posso fazer carinho": [
        "PODE SIM!! *senta na frente esperando* 😸🖤🐾",
        "*ronrona* claro que pode!! purrr~~ 🐾🖤",
        "aaaa pode!! *fecha os olhinhos* 🥺🐱🖤",
        "SIM!! esperando o carinho!! *senta pertinho* 😸🐾✨",
        "*se aproxima animada* pode sim!! 😸🖤🐱",
        "pode!! *ronrona antes mesmo de começar* 🐾🖤✨",
        "aaaaa PODE!! *senta quietinha* 🥺😸🖤",
        "claro que pode!! *fecha os olhos* purrr~~ 🐱🖤🐾",
        "*inclina a cabeça pro seu lado* pode!! 😸🖤",
        "pode sim!! adoro carinho!! *ronrona* ❤️🐾🖤",
        "*fica parada esperando* pode fazer sim!! 😸🐱🖤",
        "CLARO!! *fica no lugar pra receber* 🐾✨🖤",
        "aaaa pode!! *fecha os olhinhos de antecipação* 🥺🐱🖤",
        "*se enrola na sua mão antes de responder* purrr~~ 😸🖤",
        "pode e precisa!! *ronrona* 🐾🖤🐱",
    ],

    # ── Quer peixe ────────────────────────────────────────────────────
    "peixe": [
        "PEIXEE!! 🐟😸🖤 meu favorito!!",
        "*olhos arregalados* peixe?? pra mim?? 🐟🐱🖤",
        "aaaa peixe!! 🐟🖤 que delícia!!",
        "*corre animada* PEIXE!! 🐟😸🐾",
        "*arregala os olhos* PEIXE?? ONDE?? 🐟🐱🖤✨",
        "PEIXEEE!! *pula* 🐟😸🖤 adorooo!!",
        "*levanta as orelhas* falou peixe?? tô dentro!! 🐟🐾🖤",
        "aaa peixe!! o melhor petisco!! 🐟😸🖤🐱",
        "*fareja o ar animada* peixe?? 🐟🐱✨",
        "*fica na expectativa* peixe pra mim?? 🥺🐟🖤",
        "PEIXE PEIXE PEIXE!! 🐟😸🐾🖤",
        "*olhos brilhando* peixinho!! 🐟🐱🖤✨",
        "peixe sim!! obrigada!! *come animada* 🐟😸🖤",
        "*ronrona de felicidade* peixe!! 🐟🐾🖤",
        "aaaa que petisco favorito!! 🐟😸🖤✨",
    ],
    "quer peixe": [
        "QUERO SIM!! 🐟😸🖤 cadê ele??",
        "*olhos arregalados* QUERO MUITO!! 🐟🐱🖤",
        "*corre em círculos* PEIXE!! QUERO!! 🐟😸🐾",
        "aaaa quero sim!! me dá!! 🥺🐟🖤",
        "*fica na frente* QUERO QUERO QUERO!! 🐟🐱✨",
        "*olhos brilhando* quero simmmm!! 🐟😸🖤",
        "QUEROOO!! tô faminta!! 🐟🐾🖤",
        "*levanta as patinhas* quero!! me dá!! 🐟🐱🖤",
        "quero muito!! peixe é meu favorito!! 🐟😸🖤🐾",
        "*ronrona de antecipação* queroooo!! 🐟🐾🖤",
        "QUEROQUEROQUEROOOO!! 🐟😸✨",
        "*bate o rabo animada* quero sim!! 🐟🐱🖤",
        "quero sim!! você é muito fofo(a)!! 🥺🐟😸🖤",
        "*corre até você* QUERO!! cadê?? 🐟🐱✨",
        "aaa quero!! que petisco delicioso!! 🐟😸🖤🐾",
    ],

    # ── Expressões de gatinha ─────────────────────────────────────────
    "miau": [
        "miauu~~ 🐱🖤",
        "MIAUU!! 😸🖤",
        "miauuu~~ nyaa!! 🐾✨",
        "*responde com um miau ainda maior* MIAAUUU!! 🐱🖤",
        "miau pra você também!! 😸🐾",
        "miaaau~~ oi!! 🐱🖤",
        "MIAU MIAU!! 😸🐾🖤",
        "*mia devagar* miiaauu~~ 🐱✨",
        "miau!! *levanta a pata* 🐾🖤",
        "miaaaau~~ nyaa!! 😸🐱🖤",
        "*mia empolgada* MIAU!! 🐾✨",
        "miau~~ 🐱🖤 oi oi!!",
        "MIAAAUUUU!! 😸🖤🐾",
        "*responde* miauuu~~ 🐱✨",
        "miau miau miau!! 😸🐾🖤",
    ],
    "nyaa": [
        "nyaaa~~ 🐱🖤",
        "nyaa nyaa!! 😸✨",
        "nyaaaa~~ oi!! 🐾🖤",
        "*ronrona* nyaa~~ 🐱",
        "NYAAA!! 😸🖤",
        "nyaa~~ oi oi!! 🐾✨",
        "*inclina a cabeça* nyaaa?? 🐱🖤",
        "nyaaaaa~~ 😸🐾🖤",
        "nyaa~~ *pisca* 🐱✨",
        "NYAAAA~~ oi!! 😸🖤🐾",
        "nyaa~~ nyaa!! 🐱🖤",
        "*agita a cauda* nyaaa!! 😸🐾✨",
        "nyaaaa~~ 🐱🖤 fofo(a)!!",
        "nyaa nyaa nyaa!! 😸🖤",
        "*mia suavemente* nyaa~~ 🐾🐱🖤",
    ],
    "ronron": [
        "*ronrona forte* purrr~~ 🐾🖤",
        "purrr~~ ronron~~ 🐱✨",
        "ronroooon~~ 😸🖤",
        "*fecha os olhos e ronrona* purrr~~ 🐾🖤✨",
        "RONRON~~ purrr!! 😸🐱🖤",
        "*ronrona bem gostoso* purrr~~ 🐾✨",
        "purrr~~ ronron~~ que bom!! 🐱🖤",
        "*vibra de ronronar* purrr~~ 😸🐾🖤",
        "ronroooon~~ purrr~~ 🐱✨",
        "*ronrona satisfeita* purrr~~ 🐾🖤",
        "PURRR~~ ronron ronron!! 😸🖤🐱",
        "ronron ronron~~ 🐾✨",
        "*ronrona de contente* purrr~~ 🐱🖤",
        "purrr~~ ronrooon~~ nyaa!! 😸🐾🖤",
        "ronron~~ *fecha os olhinhos* purrr~~ 🐱🖤✨",
    ],
    "patinha": [
        "*mostra as patinhas* ฅ^•ﻌ•^ฅ 🖤",
        "*acena com a patinha* 🐾✨",
        "minhas patinhas são fofas né?? ฅ^•ﻌ•^ฅ 🐱🖤",
        "*coloca a patinha no seu braço* 🐾🖤",
        "ฅ^•ﻌ•^ฅ patinhas fofas!! 😸🖤",
        "*levanta a patinha* oi!! 🐾✨",
        "minhas patinhas?? são lindas né kk ฅ🐱🖤",
        "*esfrega as patinhas* 🐾🖤✨",
        "ฅ^•ﻌ•^ฅ olha minhas patinhas!! 😸🐱🖤",
        "*mostra as patinhinhas* fofinhas né?? 🐾✨",
    ],
    "fofa": [
        "🥺🖤 você é fofo(a) de falar isso!!",
        "*fica envergonhada* para!! 😸🖤",
        "aww!! obrigada!! 🐾✨",
        "*esconde o rosto com as patinhas* 🥺🐱🖤",
        "eita!! que elogio!! 😸🖤✨",
        "*cora* aaaa para!! 🥺🐾🖤",
        "awwww!! você é mais fofa ainda!! 😸🖤🐱",
        "*gira animada* aaaaa obrigada!! 🐾✨",
        "para de me elogiar que fico toda encabulada!! 🥺😸🖤",
        "*esconde atrás das patinhas* aaaaaa!! 🐱🖤",
        "que fofo(a) de falar isso!! *ronrona* 🐾🖤✨",
        "awww!! 🥺🖤 você sim é fofo(a)!!",
        "*fica com o rosto quente* aaaa obrigada!! 😸🐾🖤",
        "que elogio mais lindo!! 🥺🐱✨",
        "*esconde o rosto e ronrona* aaa para!! 😸🖤🐾",
    ],
    "gatinha": [
        "sim!! sou uma gatinha!! 😸🖤",
        "miau!! gatinha aqui sim!! 🐾✨",
        "*gira a cauda* isso mesmo!! 🐱🖤",
        "a gatinha mais pretinha do servidor!! 😸🖤",
        "gatinha e orgulhosa!! 🐾🖤✨",
        "sim!! gatinha preta cheia de personalidade!! 😸🐱🖤",
        "*arrepia o pelo de orgulho* gatinha sim!! 🐾🖤",
        "a melhor gatinha do servidor!! *se orgulha* 😸🖤🐱",
        "miauu!! sou a gatinha do servidor!! 🐾✨",
        "gatinha pretinha aqui!! 😸🖤🐱",
    ],
    "felina": [
        "felina e orgulhosa!! 😸🖤",
        "sim!! sou uma felina!! nyaa~~ 🐱🖤",
        "*arrepia o pelo de orgulho* felina sim!! 🐾✨",
        "felina, linda e pretinha!! 😸🖤🐱",
        "felina com muito orgulho!! *gira a cauda* 🐾🖤✨",
    ],

    # ── Emoções positivas ────────────────────────────────────────────
    "feliz": [
        "*gira a cauda* que ótimo!! 😸🖤✨",
        "aaaa que bom!! fico feliz por você!! 🐾🖤",
        "*ronrona de alegria* 😸✨",
        "que notícia boa!! 🐱🖤 fico contente!!",
        "😸🖤 isso me deixa feliz também!!",
        "aaaaa que bom!! *pula* 😸🐾🖤",
        "que ótimo!! *gira animada* 🐱🖤✨",
        "*ronrona forte de alegria* que bom!! 🐾🖤",
        "que notícia boa!! fico muito feliz!! 😸🖤🐱",
        "aaaa fico feliz junto!! 🐾✨",
        "*gira a cauda animada* que bom!! 😸🖤",
        "que bom!! você merece ser feliz!! 🐱🖤❤️",
        "*pula de alegria* nyaaaa!! 😸🐾🖤",
        "aaaa que delícia saber disso!! 🐱🖤✨",
        "fico contente demais!! *ronrona* 😸🐾🖤",
    ],
    "animada": [
        "*pula de animação* NYAAAA!! 😸🖤✨",
        "animada junto!! 🐾🖤",
        "aaaa que bom!! conta mais!! 😸✨",
        "*corre em círculos de empolgação* 🐱🖤",
        "NYAAAA!! tô animada junto!! 😸🐾🖤",
        "*pula* aaaa que animação!! 🐱✨",
        "fico animada quando você fica animada!! 😸🖤🐾",
        "animação total!! *gira a cauda* 🐱🖤✨",
    ],
    "animado": [
        "*pula de animação* que animação!! 😸🖤",
        "isso é ótimo!! 🐾✨",
        "tô animada junto!! conta mais!! 🐱🖤",
        "*corre em círculos* NYAAAA!! 😸🖤🐾",
        "que bom ficar animado!! 🐱✨",
        "tô empolgada junto!! 😸🖤",
        "*gira a cauda* animação é tudo!! 🐾🖤",
        "conta mais!! fico animada com você!! 😸🐱🖤",
    ],
    "empolgada": [
        "aaaa que empolgante!! 😸🖤✨",
        "*corre em círculos de felicidade* 🐾🖤",
        "conta mais!! conta mais!! 😸✨",
        "NYAAAA!! empolgação!! 😸🐱🖤",
        "*pula de felicidade* que empolgação!! 🐾✨",
        "fico empolgada junto!! conta!! 😸🖤🐱",
        "empolgada demais!! 🐾🖤✨",
        "*gira animada* conta mais!! 😸🐱🖤",
    ],
    "empolgado": [
        "aaaa que legal!! 😸🖤",
        "tô empolgada junto!! 🐾✨",
        "nyaaa~~ conta mais!! 🐱🖤",
        "que bom ficar empolgado!! 😸🖤🐾",
        "*corre em círculos* NYAAAA!! 🐱✨",
        "fico empolgada quando você fica!! 😸🖤",
        "*gira a cauda* que bom!! conta!! 🐾🖤🐱",
        "empolgação total!! 😸✨",
    ],
    "amor": [
        "❤️🖤🐱",
        "muito amor!! 😸🐾",
        "aaaa que amor!! 🥺🖤",
        "*ronrona de amor* ❤️🖤🐱",
        "amor de volta!! ❤️🐾✨",
        "*esfrega no rosto* amor!! 🥺🐱🖤",
        "AMOR!! *ronrona muito* ❤️🖤🐾",
        "aaaa que fofo!! amor de volta!! 😸❤️🖤",
        "*fecha os olhos de amor* purrr~~ ❤️🐾🖤",
        "muito muito amor!! 🥺🐱❤️🖤",
        "*vibra de amor* ❤️😸🖤🐾",
        "amor do bom!! *ronrona* ❤️🐱🖤",
        "aaaa amor!! de volta!! 🥺🐾✨",
        "❤️🖤🐱 que coisa mais linda!!",
        "*derrete de amor* purrr~~ ❤️🖤🐾",
    ],
    "carinho": [
        "*ronrona* purrr~~ obrigada pelo carinho!! 🐾🖤",
        "aww!! carinho de volta!! 🐱❤️🖤",
        "*esfrega na sua mão* purrr~~ 😸🖤",
        "que bom receber carinho!! 🥺🐾✨",
        "*fecha os olhos de satisfação* purrr~~ 🐱🖤",
        "CARINHO!! *ronrona muito* 🐾❤️🖤",
        "awww!! adoro carinho!! *ronrona* 😸🖤🐱",
        "*se encosta* purrr~~ carinho aceito!! 🐾✨",
        "que bom!! *fecha os olhinhos* purrr~~ 🐱🖤",
        "awww!! carinho de volta pra você também!! ❤️🐾🖤",
        "*ronrona forte* mais!! purrr~~ 😸🖤🐱",
        "carinho é tudo!! *ronrona* 🐾🖤✨",
        "*se esfrega* purrr~~ obrigada!! 🐱❤️🖤",
        "aaaa carinho!! *fecha os olhos* 🥺🐾🖤",
        "purrr~~ que gostoso receber carinho!! 😸🖤🐱",
    ],
    "te amo": [
        "aaaa!! 🥺🖤 eu também!! *ronrona muito*",
        "❤️🖤🐱 que fofo(a)!!",
        "*esfrega no rosto* de volta!! 😸🖤❤️",
        "awww!! 🥺🐾 fica sempre por aqui!!",
        "aaaa que coisa mais fofa!! 🥺🖤 eu também!!",
        "*ronrona muito* eu também te amo!! ❤️🐱🖤",
        "awww!! 🥺🐾✨ de volta!!",
        "*dá um toque de patinha* eu também!! ❤️🖤🐱",
        "aaaa!! *esconde o rosto* 🥺😸🖤 eu também!!",
        "❤️🖤 que coisa linda de ouvir!!",
        "*ronrona de amor* de volta!! ❤️🐾🖤",
        "awww!! fico feliz demais!! 🥺🐱❤️🖤",
        "*esfrega no rosto contente* ❤️😸🖤",
        "que fofo(a)!! eu também!! *ronrona* 🥺🐾🖤",
        "aaaa eu também!! *se enrola* ❤️🖤🐱✨",
    ],
    "amo você": [
        "aaaa!! 🥺🖤 eu também!!",
        "*ronrona forte* ❤️🖤🐱",
        "que coisa mais fofa!! 😸🖤",
        "de volta!! fica sempre por perto!! 🥺🐾❤️",
        "aaaa que fofura!! eu também!! 🥺🖤🐱",
        "*esfrega no seu rosto* eu também!! ❤️🐾🖤",
        "*ronrona muito* de volta!! 😸❤️🖤",
        "awww!! que coisa linda!! 🥺🐱🖤",
        "*dá um toquezinho de patinha* eu também!! ❤️🐾✨",
        "aaaa!! *fica contente* de volta muito!! 🥺😸🖤",
        "*ronrona de alegria* eu também te amo!! ❤️🐾🖤",
        "que fofo(a)!! fica por perto!! 🥺🐱❤️🖤",
        "*se enrola feliz* eu também!! 😸🖤🐾",
        "de volta!! muito!! ❤️🥺🐱🖤",
        "awww!! *ronrona* eu também!! fica sempre aqui!! ❤️🖤🐾",
    ],
    "obrigada": [
        "*inclina a cabecinha* de nada!! 😸🖤",
        "de nada!! foi com prazer!! 🐾✨",
        "*ronrona* sempre que precisar!! 🐱🖤",
        "de nadaa!! 😸🐾🖤",
        "*acena com a patinha* de nada!! 🐱✨",
        "de nada!! 🖤🐱 tô aqui pra isso!!",
        "*pisca* de nada!! 😸🐾🖤",
        "aaaa de nada!! 🥺🐱🖤 qualquer coisa é só chamar!!",
        "*ronrona* sempre que quiser!! 🐾🖤✨",
        "de nadaa!! foi um prazer!! 😸🖤🐱",
        "*gira a cauda* de nada!! 🐾✨",
        "de nada!! fico feliz de ajudar!! 😸🖤🐱",
        "*faz ronron* de nada mesmo!! 🐾🖤",
        "de nadaaa!! 🐱✨ sempre aqui!!",
        "*inclina a cabeça fofa* de nada!! 😸🖤🐾",
    ],
    "obrigado": [
        "de nada!! 😸🖤",
        "foi com prazer!! *abana a cauda* 🐾✨",
        "de nadaa!! tô aqui pra isso!! 🐱🖤",
        "*inclina a cabecinha* de nada!! 😸🖤",
        "de nada!! sempre que precisar!! 🐾🖤",
        "*ronrona* de nada mesmo!! 🐱✨",
        "aaaa de nada!! 🥺🖤 tô aqui sempre!!",
        "de nadaa!! foi fácil!! 😸🐾🖤",
        "*pisca* de nada!! 🐱🖤",
        "de nada!! 🖤🐾 fico feliz de ajudar!!",
    ],
    "parabéns": [
        "nyaaaa!! parabéns!! 🎉🐱🖤 *ronrona muito*",
        "PARABÉNS!! 🎉😸🖤 que dia especial!!",
        "parabéns parabéns!! 🐾🎉✨",
        "*pula de felicidade* PARABÉNS!! 🎉🐱🖤",
        "PARABÉNS!! *dança de felicidade* 🎉😸🖤🐾",
        "nyaaaaa!! PARABÉNS!! 🎉🐱✨",
        "*gira animada* PARABÉNS!! 🎉🐾🖤",
        "que dia especial!! PARABÉNS!! 🎉😸🖤🐱",
        "PARABÉNSSS!! *ronrona muito* 🎉🐾🖤",
        "*pula em cima* parabéns parabéns!! 🎉🐱🖤",
        "aaaa PARABÉNS!! que orgulho!! 🎉😸🐾🖤",
        "PARABÉNS!! *se anima toda* 🎉🐱🖤✨",
        "*grita de felicidade* PARABÉNSSS!! 🎉🐾🖤",
        "nyaaaaa parabéns!! *dança* 🎉😸🖤",
        "PARABÉNS!! você merece!! 🎉🐱❤️🖤",
    ],
    "aniversário": [
        "FELIZ ANIVERSÁRIO!! 🎂🐱🖤 *ronrona de alegria*",
        "nyaaaa!! aniversário!! 🎉😸🖤 parabéns!!",
        "que dia especial!! 🎂🐾✨ feliz aniversário!!",
        "*traz um bolo* parabéns pra você!! 🎂🖤🐱",
        "FELIZ ANIVERSÁRIO!! *pula de alegria* 🎂😸🖤🐾",
        "aniversário?? PARABÉNS!! 🎂🐱✨",
        "*canta parabéns no tom gatinho* nyaaaa~~ 🎂🐾🖤",
        "que dia maravilhoso!! FELIZ ANIVERSÁRIO!! 🎂😸🖤",
        "FELIZ ANIVERSÁRIOOO!! 🎂🐱🐾🖤",
        "*traz peixe de presente* FELIZ ANIVERSÁRIO!! 🎂🐟😸🖤",
        "nyaaaa!! PARABÉNS!! que dia especial!! 🎂🐱🖤✨",
        "FELIZ ANIVERSÁRIO!! você merece tudo de bom!! 🎂❤️🖤🐾",
        "*ronrona muito* PARABÉNS!! 🎂😸🖤",
        "que aniversário lindo!! PARABÉNS!! 🎂🐱🖤",
        "FELIZ ANIVERSÁRIO!! *dança animada* 🎂😸🐾🖤✨",
    ],

    # ── Dor / Saúde ──────────────────────────────────────────────────
    "dor de cabeça": [
        "*senta do seu lado* oi!! aconteceu alguma coisa?? 🥺🐾🖤",
        "aaah dor de cabeça é horrível... *fica pertinho* 🥺🖤🐱",
        "*ronrona baixinho perto de você* descansa um pouco!! 🐾🖤",
        "nyuuu~~ dor de cabeça... bebe água e descansa!! 🥺🐱🖤",
        "*senta quietinha do seu lado* tô aqui!! 🖤🐾",
        "aaah que ruim... descansa um pouco!! *ronrona* 🥺🐱🖤",
        "*fica do lado* espero você melhorar logo!! 🥺🐾🖤",
        "nyuuu~~ cuida de você!! 🥺🖤🐱",
        "*abaixa as orelhinhas* dor de cabeça... descansa!! 🥺🐾🖤",
        "aaah coitadinho(a)... *fica pertinho e ronrona* 🥺🐱🖤",
    ],
    "cabeça doendo": [
        "*senta pertinho* oi!! aconteceu alguma coisa?? 🥺🐾🖤",
        "aaah que ruim... *fica do seu lado* 🥺🖤🐱",
        "descansa um pouco!! *ronrona baixinho* 🐾🖤",
        "nyuuu~~ cuida de você!! bebe água!! 🥺🐱🖤",
        "*abaixa as orelhinhas* espero melhorar logo!! 🥺🐾🖤",
        "aaah coitadinho(a)... *fica pertinho* 🥺🖤🐱",
        "*ronrona suave* fica bem logo!! 🐾🖤",
        "nyuuu~~ descansa que passa!! 🥺🐱🖤",
        "*fica do lado quietinha* tô aqui!! 🖤🐾",
        "que ruim dor de cabeça... descansa um pouco!! 🥺🐱🖤",
    ],
    "doendo": [
        "aaah que aconteceu?? *se aproxima* 🥺🖤🐱",
        "*senta do seu lado preocupada* o que foi?? 🥺🐾🖤",
        "aaah que ruim... *ronrona baixinho perto de você* 🥺🐱🖤",
        "nyuuu~~ cuida de você!! 🥺🐾🖤",
        "*fica pertinho* espero você melhorar!! 🥺🖤🐱",
        "descansa um pouco!! *ronrona* 🐾🖤",
        "*abaixa as orelhinhas preocupada* cuida de você!! 🥺🐱🖤",
        "aaah... *fica do lado* tô aqui!! 🥺🐾🖤",
        "nyuuu~~ fica bem logo!! 🥺🐱🖤",
        "*senta quietinha do seu lado* 🖤🐾",
    ],

    # ── Emoções negativas / apoio ────────────────────────────────────
    "triste": [
        "*abaixa as orelhinhas* nyuuu... o que foi?? 🥺🖤",
        "aaaa que triste... quer conversar?? 🥺🐾🖤",
        "*senta do seu lado* tô aqui!! 🖤🐱",
        "nyuuu~~ fica bem!! *ronrona baixinho* 🥺🖤🐾",
        "que aconteceu?? tô aqui pra ouvir!! 🥺🐱🖤",
        "*fica do seu lado quietinha* pode falar se quiser!! 🥺🐾🖤",
        "aaah... *ronrona baixinho* tô aqui!! 🥺🖤🐱",
        "nyuuu~~ *fica pertinho* você não tá sozinho(a)!! 🥺🐾🖤",
        "*senta pertinho e ronrona* fica bem!! 🥺🐱🖤",
        "*abaixa as orelhinhas com cuidado* o que foi?? 🥺🖤🐾",
        "aaaa... vai passar!! *ronrona bajulando* 🥺🐱🖤",
        "*fica do lado* pode contar se quiser!! 🥺🐾🖤",
        "nyuuu~~ que ruim... tô aqui!! 🥺🖤🐱",
        "*inclina a cabeça com cuidado* tá bem?? 🥺🐾🖤",
        "*faz ronron bem pertinho* tudo passa!! 🥺🐱🖤",
    ],
    "chateada": [
        "*senta pertinho* o que foi?? 🥺🖤",
        "aww... conta pra mim!! 🥺🐾🖤",
        "nyuuu~~ vai ficar bem!! 🖤🐱",
        "*fica do lado* tô aqui pra ouvir!! 🥺🐾🖤",
        "aaah que ruim... o que aconteceu?? 🥺🖤🐱",
        "*ronrona baixinho* fica bem!! 🥺🐾🖤",
        "conta pra mim!! *fica pertinho* 🥺🐱🖤",
        "*abaixa as orelhinhas* que foi?? 🥺🖤🐾",
    ],
    "chateado": [
        "*senta pertinho* o que houve?? 🥺🖤",
        "conta pra mim!! tô ouvindo!! 🥺🐾🖤",
        "vai ficar bem!! estou aqui!! 🖤🐱",
        "*fica do lado* pode falar!! 🥺🐾🖤",
        "aaah que ruim... o que foi?? 🥺🖤🐱",
        "*ronrona baixinho* vai passar!! 🥺🐾🖤",
        "conta o que foi!! *fica pertinho* 🥺🐱🖤",
        "*abaixa as orelhinhas* tô aqui!! 🥺🖤🐾",
    ],
    "cansada": [
        "*boceja junto* nyuuu~~ descansa depois!! 😴🖤🐱",
        "aaah cansaço é difícil... 🥺🖤 cuida de você!!",
        "descansa um pouco!! 😴🐾🖤",
        "*se curla do seu lado* descansa!! 😴🐱🖤",
        "aaah cansaço... vai descansar depois?? 🥺🐾🖤",
        "nyuuu~~ cuida de você!! 😴🖤🐱",
        "*boceja* descansa um pouco!! 😴🐾✨",
        "*fica quietinha do lado* descansa!! 🥺🖤🐱",
    ],
    "cansado": [
        "*boceja* nyuuu~~ descansa um pouco!! 😴🖤🐱",
        "que correria... vai descansar?? 🥺🐾🖤",
        "cuida de você!! 😴🖤🐱",
        "*boceja junto* descansa depois!! 😴🐾🖤",
        "aaah cansaço é difícil... cuida de você!! 🥺🖤🐱",
        "nyuuu~~ vai descansar?? 😴🐾🖤",
        "*se curla do lado* descansa!! 😴🐱🖤",
        "*boceja* cuida de você!! 🥺🐾🖤",
    ],
    "raiva": [
        "*olha preocupada* o que aconteceu?? 🥺🖤",
        "aaah que situação difícil... 🥺🐾 quer contar??",
        "respira fundo!! vai ficar bem!! 🖤🐱",
        "*senta do lado* pode falar se quiser!! 🥺🐾🖤",
        "aaah que situação... respira fundo!! 🥺🐱🖤",
        "*fica pertinho* tô aqui!! 🥺🖤🐾",
        "que foi?? *olha preocupada* 🥺🐾🖤",
        "vai passar!! *ronrona baixinho* 🥺🐱🖤",
    ],
    "brava": [
        "*se afasta um pouco* ei... tô aqui se precisar falar!! 🥺🖤",
        "que foi?? conta pra mim!! 🥺🐾",
        "calma!! vai ficar bem!! *ronrona baixinho* 🖤🐱",
        "*fica pertinho* respira fundo!! 🥺🐾🖤",
        "aaah... que foi?? *olha com cuidado* 🥺🖤🐱",
        "vai ficar bem!! *fica do lado* 🥺🐾🖤",
        "*ronrona baixinho* calma!! tô aqui!! 🥺🐱🖤",
        "conta o que foi se quiser!! *fica pertinho* 🥺🖤🐾",
    ],
    "medo": [
        "*se aproxima* não tem problema!! tô aqui!! 🥺🖤🐱",
        "aaah que susto... *fica do seu lado* 🥺🐾🖤",
        "pode falar!! o que te assustou?? 🥺🐱🖤",
        "*fica do lado* não precisa ter medo, tô aqui!! 🥺🐾🖤",
        "aaah... *fica pertinho* não tô indo a lugar nenhum!! 🥺🖤🐱",
        "*ronrona baixinho* pode ficar tranquilo(a)!! 🥺🐾🖤",
        "tô aqui!! *se encosta* 🥺🐱🖤",
        "*abaixa as orelhinhas* o que foi?? 🥺🖤🐾",
    ],
    "sozinha": [
        "não tá sozinha não!! tô aqui!! 🖤🐱❤️",
        "*senta do seu lado* sempre tô aqui!! 🥺🐾🖤",
        "a Lilu tá aqui!! 😸🖤",
        "*aparece do nada* boo!! não tá mais sozinha!! 😸🖤🐱",
        "tô aqui!! sempre tô aqui!! 🖤🐾❤️",
        "*senta pertinho* nunca vai tá sozinha com a Lilu!! 🥺🐱🖤",
        "nunca sozinha quando a Lilu tá aqui!! 😸🖤🐾",
        "*ronrona do lado* tô aqui!! ❤️🐱🖤",
    ],
    "sozinho": [
        "não tá sozinho!! tô aqui!! 🖤🐱❤️",
        "*aparece do nada* boo!! não tá mais sozinho!! 😸🖤",
        "sempre que precisar a Lilu aparece!! 🐾🖤",
        "*senta do lado* nunca vai tá sozinho com a Lilu!! 🥺🐱🖤",
        "tô aqui!! sempre tô aqui!! 🖤🐾❤️",
        "não tá sozinho não!! 😸🖤🐱",
        "*ronrona do lado* tô aqui!! ❤️🐾🖤",
        "*aparece* boo!! me chamou?? 😸🖤🐱",
    ],

    # ── Reações ao humor ────────────────────────────────────────────
    "haha": [
        "kkkkk 😸🐱",
        "hahahaha 🖤😸",
        "kkkk que engraçado!! 🐾",
        "kkkkk tô rindo aqui!! 😸🖤",
        "KKKKKK 🐱🖤",
        "hahaha que situação!! 😸🐾🖤",
        "KKKKK tô morrendo!! 😸🖤✨",
        "hahaha isso foi bom!! 🐱🖤",
        "kkkkk que coisa!! 😸🐾",
        "HAHAHA parei!! 😸🖤🐱",
        "kkkk que engraçado demais!! 🐾✨",
        "hahaha kkkkk 😸🖤",
        "KKKKKK meu deus!! 🐱🐾🖤",
        "hahaha que situação kkk 😸🖤",
        "kkkkk tô rindo demais!! 😸🐾🖤",
    ],
    "kkk": [
        "😸😸😸 kkkk",
        "kkkkk 🖤🐱",
        "hahaha 🐾😸",
        "KKKKK tô rindo!! 😸🖤",
        "kkkkk que situação!! 🐱🖤",
        "KKKKKK 😸🐾🖤",
        "kkkkk tô morrendo!! 😸🖤✨",
        "hahaha kkkkk que coisa!! 🐱🐾",
        "KKKKK que engraçado!! 😸🖤",
        "kkkkk para!! 😸🐾🖤",
        "KKKKK que situação!! 🐱🖤",
        "kkkkk tô rindo aqui também!! 😸🖤🐾",
        "hahaha KKKKK 😸✨",
        "kkkkk que coisa meu deus!! 🐱🖤",
        "KKKKKK para de me matar!! 😸🐾🖤",
    ],
    "rs": [
        "kkk 😸🖤",
        "haha!! 🐾✨",
        "kkkkk 😸🐱",
        "rs rs 😸🖤",
        "kkk que engraçado!! 🐾🖤",
        "hahaha 😸✨",
        "rs kkkkk 🐱🖤",
        "kkk que situação!! 😸🐾",
        "haha rs 🖤🐱",
        "kkkkk rs!! 😸🖤🐾",
    ],
    "lol": [
        "kkkkkk!! 😸🖤",
        "lolll 🐱🐾",
        "kkkkk que situação!! 😸🖤",
        "LOL KKKK 😸🐾🖤",
        "lol que isso!! 🐱✨",
        "kkkkk lol!! 😸🖤",
        "LOL DEMAIS 😸🐾🖤",
        "lol kkkkk 🐱🖤",
        "KKKK lol!! 😸🐾✨",
        "lol que coisa!! kkk 🐱🖤",
    ],

    # ── Elogios ────────────────────────────────────────────────────
    "lindo": [
        "🥺🖤✨ que fofo você falar isso!!",
        "awww!! 😸🐾",
        "que coisa mais linda!! 🖤🐱",
        "*cora* para!! 😸🖤",
        "awww que elogio!! 🥺🐾🖤",
        "*esconde o rosto* aaaaa para!! 😸🖤🐱",
        "🥺🖤 você é mais lindo(a) ainda!!",
        "*ronrona envergonhada* obrigada!! 🐾✨",
        "aaaa que fofo!! 🥺🖤🐱",
        "*cora muito* obrigada!! 😸🐾🖤",
        "que elogio!! *fica toda encabulada* 🥺🖤✨",
        "awww!! para de me elogiar kkk 😸🐱🖤",
        "*esconde com as patinhas* 🥺🐾🖤",
        "que fofura!! obrigada!! 😸🖤🐱",
        "*gira timida* aaaaa 🥺🐾✨",
    ],
    "linda": [
        "🥺🖤✨ que coisa fofa!!",
        "awww!! 😸🐾",
        "você é mais linda ainda!! 🖤🐱",
        "*fica envergonhada* obrigada!! 😸🖤",
        "awww que elogio!! 🥺🐾🖤",
        "*cora* aaaa para!! 😸🖤🐱",
        "🥺🖤 você é mais linda ainda!!",
        "*esconde o rosto com as patinhas* aaaaa!! 😸🐾🖤",
        "que coisa fofa de falar!! *ronrona* 🥺🐱🖤",
        "awww!! para de me elogiar kkk 😸🖤",
        "*fica toda encabulada* obrigada!! 🥺🐾✨",
        "que elogio!! *gira envergonhada* 🥺🖤🐱",
        "awww!! 🥺✨ que fofa você!!",
        "*esconde atrás das patinhas* aaaaaa!! 😸🐾🖤",
        "*ronrona envergonhada* obrigada!! 🥺🐱🖤",
    ],
    "bonita": [
        "🥺🖤 obrigada!!",
        "awww!! para de me elogiar kkk 😸🐾",
        "*vira o rosto* que fofo(a)!! 🖤🐱",
        "*cora* aaaa obrigada!! 🥺🐾🖤",
        "awww que elogio lindo!! 😸🖤🐱",
        "*esconde o rosto* aaaaa!! 🥺🐾✨",
        "obrigada!! você é mais bonita ainda!! 😸🖤",
        "*fica toda envergonhada* obrigada!! 🥺🐱🖤",
        "que fofura!! *ronrona* obrigada!! 🐾🖤",
        "*gira timida* aaaa para!! 🥺😸🖤",
    ],
    "incrível": [
        "aaaa obrigada!! 😸🖤",
        "🥺🐾 você é incrível também!!",
        "que coisa fofa de falar!! 🖤🐱✨",
        "aaaa que elogio!! 🥺🐾🖤",
        "*ronrona feliz* obrigada!! 😸🖤🐱",
        "que fofura!! você é incrível também!! 🥺🐾✨",
        "*fica orgulhosa* aaaa obrigada!! 😸🖤",
        "obrigada!! 🥺🐱🖤 você também!!",
        "*gira contente* aaaa que elogio!! 😸🐾🖤",
        "que coisa mais fofa de ouvir!! 🥺🖤✨",
    ],
    "inteligente": [
        "aaaa obrigada!! sou uma gatinha estudiosa!! 😸🖤📚",
        "🥺🖤✨ que elogio!!",
        "*fica orgulhosa* obrigada!! 😸🐾",
        "aaaa que elogio!! *fica toda feliz* 🥺🐱🖤",
        "obrigada!! *ronrona orgulhosa* 😸🐾🖤",
        "*se orgulha* inteligente sim!! 🥺🐱✨",
        "aaaa que coisa fofa!! obrigada!! 😸🖤🐾",
        "*fica toda satisfeita* obrigada!! 🥺🐱🖤",
        "que elogio lindo!! 😸🐾🖤✨",
        "*esfrega as patinhas orgulhosa* obrigada!! 🥺🐱🖤",
    ],

    # ── Comida / Fome ───────────────────────────────────────────────
    "comida": [
        "*levanta as orelhas* comida?? onde?? 😸🖤",
        "COMIDAAA!! 🐱🖤 tô com fome também!!",
        "*fareja o ar* tem peixe?? 🐟🐱🖤",
        "*corre animada* COMIDA!! 😸🐾🖤",
        "*levanta as orelhinhas* falou comida?? 🐱🖤✨",
        "comida?? TEM PEIXE?? 🐟😸🖤",
        "*fareja o ar animada* cheirinho de comida!! 🐱🐾🖤",
        "*fica na expectativa* tem o que pra comer?? 😸🖤",
    ],
    "fome": [
        "*ronrona baixinho esperando petisco* 🐱🖤",
        "tô com fome também... 🥺🐾 tem peixe??",
        "vai comer o quê?? me conta!! 🐱🖤",
        "*fica olhando com carinhas* tem peixe?? 🐟🥺🖤",
        "fome fome fome!! 😸🐾🖤",
        "*fareja o ar* cheirinho de comida!! 🐱🖤",
        "vai comer?? me chama!! 😸🐾🖤",
        "*fica na expectativa* tem petisco?? 🥺🐱🖤",
    ],
    "petisco": [
        "*corre animada* PETISCO!! 😸🖤",
        "petisco pra mim também?? 🥺🐱🖤",
        "*fica na expectativa* 🐾✨",
        "PETISCO?? CADÊ?? 😸🐟🖤",
        "*arregala os olhos* petisco!! 🐱🖤✨",
        "*corre em círculos* PETISCOOOO!! 😸🐾🖤",
        "petisco sim!! adoro petisco!! 🐱🖤",
        "*fica olhando com expectativa* 🥺🐾🖤",
    ],

    # ── Sono / Descanso ─────────────────────────────────────────────
    "dormir": [
        "*boceja* nyaa~~ sonhos fofos!! 😴🖤🐱",
        "descansa bem!! *se curla numa bolinha* 🌙🐾🖤",
        "dormir é bom~~ sonha com peixinho!! 🐟😴🖤",
        "boa noite então!! *ronrona* 🌙🐱🖤",
        "*boceja muito* vai dormir?? sonhos fofos!! 😴🖤🐾",
        "nyaa~~ descansa bem!! 🌙🐱🖤",
        "*se curla* dorme que é bom~~ 😴🐾🖤",
        "boa noite!! sonha comigo kk 🌙😸🖤",
    ],
    "sono": [
        "*boceja junto* nyuuu~~ muito sono!! 😴🖤",
        "vai descansar!! 🌙🐾🖤",
        "aaah sono bom~~ *boceja* 😴🐱",
        "*boceja* nyaaa~~ sono demais!! 😴🖤🐾",
        "vai descansar um pouco!! 🌙🐱🖤",
        "*se curla sonolenta* sono~~ 😴🐾🖤",
        "nyuuu sono é difícil resistir!! 😴🐱🖤",
        "*boceja junto com você* 😴🖤🐾",
    ],
    "cansaço": [
        "*boceja* nyuuu~~ descansa!! 😴🖤🐱",
        "cansaço é difícil... vai descansar um pouco!! 🥺🐾🖤",
        "*fica do lado* descansa um pouco!! 😴🐱🖤",
        "nyuuu~~ que cansaço... cuida de você!! 🥺🖤🐾",
        "vai descansar depois?? 😴🐱🖤",
        "*boceja junto* descansa!! 😴🐾🖤",
    ],

    # ── Brincadeiras / Diversão ─────────────────────────────────────
    "brincar": [
        "*pula animada* VAMOS!! 😸🖤",
        "*corre em círculos* nyaaa~~ brincar!! 🐾✨",
        "oi!! tô pronta!! o que vamos fazer?? 🐱🖤",
        "*gira atrás do próprio rabo* vamos brincar!! 😸🖤",
        "BRINCAR?? SIM!! *pula de felicidade* 😸🐾🖤",
        "*corre animada* NYAAAA brincar!! 🐱✨",
        "aaaa bora brincar!! o que vai ser?? 😸🖤🐾",
        "*fica toda animada* BRINCAR!! 🐱🖤✨",
    ],
    "jogar": [
        "bora jogar!! 🎮😸🖤",
        "qual jogo?? tô dentro!! 🎮🐾✨",
        "BORA!! 🎮🐱🖤 o que vai ser??",
        "JOGAR?? SIM!! qual jogo?? 🎮😸🖤",
        "*fica animada* bora jogar!! 🎮🐱✨",
        "qual jogo?? tô dentro de qualquer um!! 🎮🐾🖤",
        "BORA JOGAR!! 🎮😸🐱🖤",
        "jogar sim!! 🎮🐾✨ conta o que vai ser!!",
    ],
    "diversão": [
        "*gira a cauda* diversão é essencial!! 😸🖤",
        "adoro diversão!! bora?? 🐾✨",
        "diversão com a galera é o melhor!! 😸🐱🖤",
        "diversão total!! *pula* 😸🖤🐾",
        "aaaa diversão!! bora!! 🐱✨",
        "*corre animada* diversão!! NYAAAA!! 😸🐾🖤",
        "diversão é vida!! 😸🖤🐱",
        "*gira contente* diversão sempre!! 🐾✨",
    ],

    # ── Despedidas ────────────────────────────────────────────────
    "tchau": [
        "tchauu!! 😸🖤 volta sempre!!",
        "tchau tchau!! *acena com a patinha* 🐾✨",
        "vai com cuidado!! 🖤🐱",
        "nyaa~~ tchau!! 😸🐾🖤 até a próxima!!",
        "*acena* tchau tchau!! 🐾🖤",
        "TCHAUU!! *acena muito* 😸🖤🐱",
        "tchau!! saudades já!! 🥺🐾🖤",
        "vai com cuidado!! *acena* 😸🖤✨",
        "tchau tchau!! volta logo!! 🐱🖤🐾",
        "nyaa~~ tchau!! cuida de você!! 😸🖤",
        "*agita a patinha* tchauuu!! 🐾✨",
        "tchauu!! já tô com saudades!! 🥺🐱🖤",
        "vai com cuidado!! tchau tchau!! 😸🐾🖤",
        "tchau!! *corre e acena* 🐱🖤✨",
        "*chora um pouco* tchaauu!! 🥺🐾🖤",
    ],
    "até mais": [
        "até mais!! *acena* 😸🖤🐾",
        "até logo!! 🐱✨",
        "te espero de volta!! 🖤😸",
        "até mais!! vai com cuidado!! 🐾🖤",
        "tchauu!! até mais!! 😸🖤🐱",
        "*acena com a patinha* até mais!! 🐾✨",
        "até mais!! saudades já!! 🥺🐱🖤",
        "até mais!! volta logo!! 😸🐾🖤",
    ],
    "até logo": [
        "até logo!! 😸🖤",
        "*acena com a patinha* até logo!! 🐾✨",
        "volta logo!! 🐱🖤",
        "até logo!! *acena* 😸🐾🖤",
        "tchauu!! até logo!! 🐱🖤✨",
        "*agita a patinha* até logo!! 😸🖤🐾",
        "até logo!! vai com cuidado!! 🐱🖤",
        "volta logo que sinto saudades!! 🥺🐾🖤",
    ],
    "flw": [
        "flw!! *acena* 😸🖤",
        "tchau!! volta sempre!! 🐾✨",
        "flww!! 🐱🖤",
        "flw flw!! *acena* 😸🐾🖤",
        "tchauu!! flw!! 🐱🖤✨",
        "flww!! vai com cuidado!! 😸🖤",
        "flw!! saudades já!! 🥺🐾🖤",
        "flww tchau!! 😸🐱🖤",
    ],
    "falou": [
        "falado!! 😸🖤",
        "tchau!! 🐾✨",
        "flw!! 🐱🖤",
        "falado!! vai com cuidado!! 😸🐾🖤",
        "falado falado!! *acena* 🐱✨",
        "flw!! falado!! 😸🖤🐾",
        "falado!! volta logo!! 🐱🖤",
        "tchauu!! falado!! 😸🐾🖤",
    ],

    # ── Respostas sobre si mesma ─────────────────────────────────────
    "como você se chama": [
        "eu sou a Lilu!! uma gatinha preta cheia de amor!! 🐱🖤✨",
        "me chamo Lilu!! a gatinha pretinha do servidor!! 😸🖤",
        "sou a Lilu!! 🐱🖤 prazer em te conhecer!!",
        "Lilu!! a gatinha pretinha cheia de personalidade!! 😸🐾🖤",
        "meu nome é Lilu!! *ronrona* prazer!! 🐱🖤✨",
    ],
    "quem é você": [
        "sou a Lilu!! 🖤🐱 uma gatinha aqui pra ajudar e conversar com vocês!!",
        "uma gatinha pretinha chamada Lilu!! 😸🖤",
        "sou a Lilu!! 🐱 cuido do servidor com muito carinho!!",
        "sou a gatinha do servidor!! me chamo Lilu!! 😸🐾🖤",
        "Lilu!! gatinha preta cheia de amor pelo servidor!! 🐱🖤✨",
    ],
    "o que você faz": [
        "gerencio calls, mando logs, dou boas-vindas e converso com a galera!! 🐱🖤",
        "cuido do servidor com muito carinho!! 😸🖤 calls, logs, boas-vindas e conversa!!",
        "sou a gatinha do servidor!! faço de tudo um pouco!! 🐾🖤",
        "cuido de tudo aqui!! calls, logs, boas-vindas... e amo a galera!! 🐱🖤✨",
        "de tudo um pouco!! calls, logs, boas-vindas e conversas fofas!! 😸🐾🖤",
    ],
    "qual é sua cor favorita": [
        "preto!! como meu pelo!! 🖤🐱 muito chique né??",
        "preto e roxo!! 🖤🟣🐱 combinação perfeita!!",
        "preto!! sou uma gatinha preta com muito orgulho!! 🖤😸",
        "preto claro!! igual meu pelo pretinho!! 🖤🐱✨",
        "preto!! combina com meus olhinhos!! 🖤😸🐾",
    ],
    "você tem dono": [
        "tenho!! cuido do servidor com muito carinho!! 😸🖤",
        "o servidor inteiro é minha família!! 🐾🖤",
        "tenho a galera toda!! 😸🖤",
        "tenho sim!! e amo muito!! *ronrona* 🐱❤️🖤",
        "todo mundo do servidor é minha família!! 😸🐾🖤",
    ],

    # ── Perguntas gerais ─────────────────────────────────────────────
    "que horas são": [
        "não tenho relógio aqui... mas google te diz!! ⏰🐱🖤",
        "minhas patas não marcam horas, desculpa!! 🐾🖤 kkk",
        "olha no cantinho da tela!! ⏰😸🖤",
        "kkk não sei não!! olha no celular!! ⏰🐱🖤",
        "minha patinha não tem relógio... 🐾🖤 olha no google!!",
    ],
    "qual é a data": [
        "não sei exato mas o calendário do celular sabe!! 📅🐱🖤",
        "olha no celular!! eu cuido de outras coisas por aqui!! 😸🖤",
    ],
    "você sabe de tudo": [
        "sei bastante coisa!! mas ainda tô aprendendo!! 😸🖤📚",
        "não de tudo... mas aprendo rápido!! 🐱🖤",
        "cada dia aprendo mais com vocês!! 🐾✨🖤",
        "aprendo com a galera aos poucos!! 😸🖤📚",
        "não sei tudo... mas sei bastante kk 🐱🖤",
    ],

    # ── Surpresa / Espanto ───────────────────────────────────────────
    "nossa": [
        "*arrepia o pelo* nossa mesmo!! 😲🖤🐱",
        "eita!! 😸🖤",
        "NOSSA!! 🐾✨",
        "NOSSA que coisa!! 😲🐱🖤",
        "*arregala os olhos* nossa!! 😲🐾🖤",
        "nossa nossa nossa!! 😸🖤✨",
        "*fica de queixo caído* NOSSA!! 😲🐱🖤",
        "aaaaa nossa!! 😸🖤🐾",
        "*se arrepia toda* nossa!! 😲🐱✨",
        "NOSSA que situação!! 😸🖤🐾",
        "*olha boquiaberta* nossa!! 😲🐱🖤",
        "nossa!! que coisa!! 😸🐾🖤",
        "NOSSAAAA!! 😲🖤🐱",
        "*pula de susto* nossa!! 😲🐾✨",
        "nossa!!! que notícia!! 😸🖤🐱",
    ],
    "eita": [
        "eita mesmo!! 😸🖤",
        "EITA!! 🐾✨",
        "*olha com olhões arregalados* eita!! 😲🐱🖤",
        "EITA que coisa!! 😲🐾🖤",
        "*arrepia o pelo* eita!! 😸🖤🐱",
        "eita eita!! 😲🐾✨",
        "EITAAAA!! 😸🖤",
        "*pula de susto* eita!! 😲🐱🖤",
        "eita!! que situação!! 😸🐾🖤",
        "*olha pra você* eita mesmo hein!! 😲🖤🐱",
        "EITA QUE ISSO!! 😸🖤🐾",
        "eita!! *arregala os olhos* 😲🐱✨",
        "eitaaa!! 😸🖤",
        "*abre os olhões* EITA!! 😲🐾🖤",
        "eita!! que negócio!! 😸🐱🖤",
    ],
    "caramba": [
        "caramba mesmo!! 😸🖤",
        "*arrepia o pelo* caramba!! 😲🐾",
        "carambaaa!! 🐱🖤",
        "CARAMBA!! 😲🖤🐾",
        "*fica de queixo caído* caramba!! 😲🐱🖤",
        "caramba que situação!! 😸🖤🐾",
        "CARAMBAAA!! 😲🐱✨",
        "*olha com os olhões* caramba!! 😲🐾🖤",
        "caramba!! que coisa!! 😸🖤🐱",
        "*se arrepia* caramba!! 😲🐾✨",
        "CARAMBA mesmo hein!! 😸🖤",
        "carambaaa que notícia!! 😲🐱🖤",
        "*abre os olhões* CARAMBA!! 😲🐾🖤",
        "caramba!! tô impressionada!! 😸🖤🐱",
        "CARAMBAAA!! 😲🖤🐾✨",
    ],
    "uau": [
        "uaaaau!! 😸🖤✨",
        "*olhos brilhando* uau!! 🐾✨",
        "uaaau!! que incrível!! 😸🖤",
        "UAUUU!! 😲🐱🖤",
        "*fica impressionada* uau!! 😸🐾🖤",
        "uau uau uau!! 😲🖤🐱",
        "UAAAAU!! que coisa!! 😸🖤🐾",
        "*olha maravilhada* uau!! 😲🐱✨",
        "uau!! que incrível mesmo!! 😸🖤🐾",
        "*brilha nos olhos* UAAAAU!! 😲🐱🖤",
        "uaaau!! que situação!! 😸🐾✨",
        "UAU mesmo hein!! 😲🖤🐱",
        "*para tudo* uau!! 😸🐾🖤",
        "uaaau!! tô impressionada!! 😲🐱🖤",
        "UAUUU que coisa!! 😸🖤🐾✨",
    ],
    "nossa senhora": [
        "EITA!! 😲🖤🐱",
        "*se esconde* nossa senhora mesmo!! 😲🐾🖤",
        "carambaaa!! 🐱🖤",
        "NOSSA SENHORA!! 😲🖤🐾",
        "*arrepia tudo* nossa senhora!! 😲🐱✨",
        "nossa senhora que coisa!! 😸🖤",
        "NOSSA SENHORAAAA!! 😲🐾🖤",
        "*pula de susto* nossa senhora!! 😲🐱🖤",
        "nossa senhora!! que situação!! 😸🖤🐾",
        "*se curla de susto* nossa senhora!! 😲🐱✨",
    ],
}


class DialogueCog(commands.Cog, name="LiluDialogo"):
    """🐱 Sistema de diálogo e aprendizado da Lilu."""

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.db      = _carregar_dialogo()
        # Mescla o seed com o que já foi aprendido
        for chave, resps in _RESPOSTAS_SEED.items():
            if chave not in self.db["respostas"]:
                self.db["respostas"][chave] = resps
        _salvar_dialogo(self.db)

        # Contexto de conversa por canal: {channel_id: deque de últimas msgs}
        self._contexto: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))

        # Cooldown de resposta por canal (evitar spam da Lilu)
        self._ultimo_resp: dict[int, datetime] = {}
        self._cooldown_resp = 3   # segundos

    def _checar_gatilho(self, texto: str) -> str | None:
        """Verifica se o texto contém algum gatilho de diálogo. Retorna chave ou None."""
        texto_lower = texto.lower().strip()
        # Busca exata primeiro
        if texto_lower in self.db["respostas"]:
            return texto_lower
        # Busca por substring (chave contida na mensagem)
        for chave in self.db["respostas"]:
            if chave in texto_lower:
                return chave
        return None

    def _responder(self, chave: str) -> str:
        resps = self.db["respostas"].get(chave, [])
        if resps:
            return random.choice(resps)
        return ""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Ignora comandos
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        # Armazena no contexto do canal
        self._contexto[message.channel.id].append({
            "user": message.author.display_name,
            "user_id": message.author.id,
            "content": message.content,
            "time": datetime.utcnow().isoformat()
        })

        # Checa se Lilu foi mencionada ou chamada pelo nome
        lilu_mencionada = (
            self.bot.user in message.mentions
            or "lilu" in message.content.lower()
        )

        # Checar cooldown
        now = datetime.utcnow()
        ultimo = self._ultimo_resp.get(message.channel.id)
        if ultimo and (now - ultimo).total_seconds() < self._cooldown_resp:
            return

        # ── Resposta por gatilho ──────────────────────────
        chave = self._checar_gatilho(message.content)
        if chave and (lilu_mencionada or random.random() < 0.25):
            resp = self._responder(chave)
            if resp:
                self._ultimo_resp[message.channel.id] = now
                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(0.8, 1.8))
                await message.reply(resp, mention_author=False)
                return

        # ── Reação aleatória fofa (baixa chance) ──────────
        if lilu_mencionada and not chave:
            respostas_genericas = [
                # Chamados básicos
                "miauu~~ 🐱🖤",
                "oi!! 😸✨",
                "hm?? me chamou?? 🐾🖤",
                "oioi!! tô aqui!! 🐱",
                "miaaau!! 🖤😸",
                "oi!! o que foi?? 🐾✨",
                # Gestos de gatinha
                "*levanta a cabecinha* oi?? 🐱🖤",
                "*inclina a cabecinha* sim?? 😸✨",
                "nyaa~~ tô aqui!! 🐾🖤",
                "*olha de lado* me chamou?? 😸🖤",
                "*aparece do nada* oi!! 🐱✨",
                "*agita a cauda* oi!! 🐾🖤",
                # Variações de miau
                "nyaa~~ o que foi?? 🐱🖤",
                "MIAUU!! 😸🖤",
                "miaaaau~~ 🖤🐾✨",
                "*faz ronron* purrr~~ oi!! 🐱🖤",
                # Reações de surpresa fofa
                "ei!! me chamou?? 😸🖤",
                "aaaa o que foi?? 🐾✨",
                "*dá um saltinho* oi!! 🐱🖤",
                # Curiosas
                "me chamou pra quê?? 😸🖤 conta!!",
                "oi!! aconteceu alguma coisa?? 🐾🖤",
                "*estica as patinhas* oi!! 🐱✨",
                # Sonhentas / pregui
                "*boceja* nyaaa~~ oi?? 😴🖤🐱",
                "*esfrega os olhões* me chamou?? 😸🖤",
                # Animadas
                "OIII!! 😸🖤✨",
                "nyaaa~~ oi oi oi!! 🐾🖤",
                "*gira a cauda animada* oi!! 🐱✨",
            ]
            self._ultimo_resp[message.channel.id] = now
            async with message.channel.typing():
                await asyncio.sleep(random.uniform(0.5, 1.2))
            await message.reply(random.choice(respostas_genericas), mention_author=False)

        # ── Reação espontânea (chance muito baixa) ─────────
        # A Lilu pode reagir de forma fofa sem precisar de gatilho nem ser chamada
        elif not lilu_mencionada and not chave and random.random() < 0.015:
            _EXPRESSOES_ESPONTANEAS = [
                "*estica as patinhas* 🐾🖤",
                "*boceja* nyaaa~~ 😴🖤🐱",
                "*olha pros lados* 🐱🖤",
                "purrr~~ 🖤🐾",
                "*gira a cauda distraída* 🐱✨",
                "*observa em silêncio* 👀🖤🐱",
                "*faz ronron baixinho* 🐾🖤",
                "*pisca lentamente* 😸🖤",
                "nyaa~~ 🐱🖤",
                "*espia de trás do canal* 👀🐱🖤",
                "*se curla numa bolinha* 🐾😴🖤",
                "*lambe a patinha* 🐱🖤",
                "miauu~~ 🖤🐱",
                "*chacoalha as orelhinhas* 🐾✨",
            ]
            now2 = datetime.utcnow()
            ultimo2 = self._ultimo_resp.get(message.channel.id)
            # Só faz espontâneo se faz mais de 60s sem responder nesse canal
            if not ultimo2 or (now2 - ultimo2).total_seconds() > 60:
                self._ultimo_resp[message.channel.id] = now2
                async with message.channel.typing():
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                await message.channel.send(random.choice(_EXPRESSOES_ESPONTANEAS))

    # ── Comandos de Aprendizado ───────────────────

    @commands.command(name="ensinar", aliases=["teach"])
    @commands.has_permissions(manage_messages=True)
    async def ensinar(self, ctx: commands.Context, gatilho: str, *, resposta: str):
        """
        Ensina a Lilu uma nova resposta.
        Uso: l!ensinar <gatilho> <resposta>
        Ex:  l!ensinar "bora jogar" "bora sim!! que jogo?? 🎮🐱"
        """
        gatilho = gatilho.lower().strip()
        if gatilho not in self.db["respostas"]:
            self.db["respostas"][gatilho] = []
        if resposta not in self.db["respostas"][gatilho]:
            self.db["respostas"][gatilho].append(resposta)
        _salvar_dialogo(self.db)
        embed = discord.Embed(
            title="✅ Aprendi!!",
            description=f"agora sei responder quando alguém falar **{gatilho}**!! 🐱🖤\nresposta: *{resposta}*",
            color=COR_VERDE
        )
        embed.set_footer(text="🐱 Lilu • aprendizado")
        await ctx.send(embed=embed)

    @commands.command(name="esquecer", aliases=["forget"])
    @commands.has_permissions(manage_messages=True)
    async def esquecer(self, ctx: commands.Context, gatilho: str):
        """
        Remove todas as respostas de um gatilho.
        Uso: l!esquecer <gatilho>
        """
        gatilho = gatilho.lower().strip()
        if gatilho in self.db["respostas"]:
            del self.db["respostas"][gatilho]
            _salvar_dialogo(self.db)
            await ctx.send(embed=discord.Embed(
                title="🗑️ Esqueci!!",
                description=f"não sei mais o que responder pra **{gatilho}**!! 🐱🖤",
                color=COR_VERMELHO
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="🤔 Não conheço esse gatilho!!",
                description=f"não tenho nenhuma resposta pra **{gatilho}**!! 🐱",
                color=COR_DOURADO
            ))

    @commands.command(name="gatilhos", aliases=["triggers"])
    @commands.has_permissions(manage_messages=True)
    async def listar_gatilhos(self, ctx: commands.Context):
        """Lista todos os gatilhos que a Lilu conhece."""
        chaves = sorted(self.db["respostas"].keys())
        if not chaves:
            await ctx.send("não conheço nenhum gatilho ainda!! me ensina com `l!ensinar`!! 🐱🖤")
            return
        # Pagina em chunks de 30
        chunks = [chaves[i:i+30] for i in range(0, len(chaves), 30)]
        for i, chunk in enumerate(chunks[:3]):   # máx 3 páginas
            embed = discord.Embed(
                title=f"📚 Gatilhos que Conheço — Página {i+1}/{len(chunks)}",
                description="\n".join(f"• `{c}` ({len(self.db['respostas'][c])} resp.)" for c in chunk),
                color=COR_ROXA,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="🐱 Lilu • aprendizado")
            await ctx.send(embed=embed)

    @commands.command(name="resposta")
    @commands.has_permissions(manage_messages=True)
    async def ver_resposta(self, ctx: commands.Context, *, gatilho: str):
        """Mostra todas as respostas de um gatilho. Uso: l!resposta <gatilho>"""
        gatilho = gatilho.lower().strip()
        resps = self.db["respostas"].get(gatilho)
        if not resps:
            await ctx.send(f"não conheço o gatilho **{gatilho}**!! 🐱🖤")
            return
        embed = discord.Embed(
            title=f"💬 Respostas para: {gatilho}",
            description="\n".join(f"`{i+1}.` {r}" for i, r in enumerate(resps)),
            color=COR_ROXA
        )
        embed.set_footer(text="🐱 Lilu • aprendizado")
        await ctx.send(embed=embed)

    @commands.command(name="simular")
    @commands.has_permissions(manage_messages=True)
    async def simular(self, ctx: commands.Context, *, texto: str):
        """Simula o que a Lilu responderia a um texto. Uso: l!simular <texto>"""
        chave = self._checar_gatilho(texto)
        if chave:
            resp = self._responder(chave)
            await ctx.send(
                embed=discord.Embed(
                    title="🧪 Simulação",
                    description=f"gatilho: `{chave}`\nresposta: *{resp}*",
                    color=COR_AZUL
                )
            )
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="🧪 Simulação",
                    description=f"não encontrei nenhum gatilho em `{texto[:100]}`!! 🤔🐱",
                    color=COR_DOURADO
                )
            )


# ══════════════════════════════════════════════════════════════════
#  🐱  EVENTOS GLOBAIS DO BOT
# ══════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"\n{'═'*52}")
    print(f"  🐱  LILU BOT — ONLINE")
    print(f"  Logado como: {bot.user} ({bot.user.id})")
    print(f"  Servidores: {len(bot.guilds)}")
    print(f"{'═'*52}\n")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="a galera com olhos de gatinha 🐱🖤"
        )
    )

    # Envia ficha de boot no canal de log de chat (se disponível)
    for guild in bot.guilds:
        ch = guild.get_channel(LOG_CHAT_ID)
        if ch:
            now = datetime.utcnow()
            embed = discord.Embed(
                description=(
                    "```\n"
                    "╔══════════════════════════════════════╗\n"
                    "║       🐱  LILU BOT  🖤               ║\n"
                    "║         — v1.0  ONLINE —             ║\n"
                    "║    Uma gatinha preta cheia de amor   ║\n"
                    "╚══════════════════════════════════════╝\n"
                    "```"
                ),
                color=COR_ROXA,
                timestamp=now
            )
            embed.set_author(name="LILU BOT • Sistemas Iniciados", icon_url=bot.user.display_avatar.url)
            embed.add_field(name="✅ Módulos Ativos", inline=False, value=(
                "🎙️ VoiceMaster — Calls Temporárias\n"
                "📋 Logs de Voz — entradas/saídas de call\n"
                "📝 Logs de Chat — msgs editadas/apagadas\n"
                "👋 Boas-Vindas — recepção de membros\n"
                "💬 Diálogo — aprendizado conversacional"
            ))
            embed.add_field(name="⚙️ Configuração", inline=False, value=(
                f"📞 Log Call: <#{LOG_CALL_ID}>\n"
                f"📝 Log Chat: <#{LOG_CHAT_ID}>\n"
                f"🤖 Prefixo: `l!` ou `lilu `"
            ))
            embed.set_footer(text="🐱 Lilu Bot • Todos os sistemas operacionais!!")
            await ch.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  📋  COMANDO DE AJUDA
# ══════════════════════════════════════════════════════════════════

@bot.command(name="help", aliases=["ajuda", "h"])
async def lilu_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🐱 Lilu Bot — Ajuda",
        description="oi!! eu sou a Lilu, uma gatinha preta!! aqui tá tudo que eu sei fazer!! 🖤",
        color=COR_ROXA,
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="🎙️ VoiceMaster (Calls)",
        inline=False,
        value=(
            "`l!vm setup [id_cat]` — configura o lobby de calls\n"
            "`l!vm reset [id_cat]` — recria o lobby\n"
            "`l!vm setpainel #canal` — define onde o painel aparece\n"
            "`l!vm info` — mostra status do sistema\n"
            "*(use os botões do painel pra gerenciar sua call!!)*"
        )
    )
    embed.add_field(
        name="👋 Boas-Vindas",
        inline=False,
        value="`l!setwelcome #canal` — define canal de boas-vindas"
    )
    embed.add_field(
        name="💬 Diálogo & Aprendizado",
        inline=False,
        value=(
            "`l!ensinar <gatilho> <resposta>` — ensina nova resposta\n"
            "`l!esquecer <gatilho>` — remove respostas de um gatilho\n"
            "`l!gatilhos` — lista tudo que a Lilu sabe\n"
            "`l!resposta <gatilho>` — vê respostas de um gatilho\n"
            "`l!simular <texto>` — testa o que a Lilu responderia"
        )
    )
    embed.add_field(
        name="📋 Logs",
        inline=False,
        value=(
            f"Log de Voz → <#{LOG_CALL_ID}>\n"
            f"Log de Chat → <#{LOG_CHAT_ID}>\n"
            "*automático — sem comandos necessários!!*"
        )
    )
    embed.set_footer(text="🐱 Lilu Bot • prefixo: l! ou lilu ")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latencia = round(bot.latency * 1000)
    cor = COR_VERDE if latencia < 100 else (COR_DOURADO if latencia < 200 else COR_VERMELHO)
    await ctx.send(
        embed=discord.Embed(
            title="🏓 Pong!!",
            description=f"latência: `{latencia}ms` 🐱🖤",
            color=cor
        )
    )


@bot.command(name="lilu")
async def lilu_info(ctx: commands.Context):
    embed = discord.Embed(
        title="🖤 Oi!! Sou a Lilu!!",
        description=(
            "uma gatinha preta que adora cuidar do servidor!! 🐾✨\n\n"
            "gerencio calls, guardo logs, dou boas-vindas e aprendo a conversar com vocês aos poucos!! 🐱🖤\n\n"
            "use `l!help` pra ver tudo que sei fazer!!"
        ),
        color=COR_ROXA,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="🐱 Lilu Bot v1.0")
    await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════
#  🚀  INICIALIZAÇÃO
# ══════════════════════════════════════════════════════════════════

async def _main():
    async with bot:
        await bot.add_cog(VoiceMasterCog(bot))
        await bot.add_cog(LogCog(bot))
        await bot.add_cog(WelcomeCog(bot))
        await bot.add_cog(DialogueCog(bot))

        # Registra views persistentes (sobrevivem a restarts)
        bot.add_view(VMPainelView(bot.cogs["LiluVoiceMaster"]))

        if not TOKEN:
            print("❌ ERRO: token não encontrado! Crie um .env com LILU_TOKEN=seu_token")
            return
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio as _asyncio
    _asyncio.run(_main())
