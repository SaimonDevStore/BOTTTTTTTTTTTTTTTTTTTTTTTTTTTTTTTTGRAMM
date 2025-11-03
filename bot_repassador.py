import os
import re
import random
import asyncio
import unicodedata
from typing import Any, Dict, List, Optional
from aiohttp import web, ClientSession
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# CONFIGURAÇÕES
TOKEN = "8378547653:AAF25X5RDPbivxqLRvQSzYrVTn4seqpqDVI"  # token do seu bot
GRUPO_ID = -1003236154348  # ID do grupo
USUARIO_AUTORIZADO = 5782277642  # seu ID

# SHOPEE - Config via variáveis de ambiente (defina no Render Settings > Environment)
SHOPEE_API_URL = os.environ.get("SHOPEE_API_URL", "")  # endpoint que lista produtos
SHOPEE_API_TOKEN = os.environ.get("SHOPEE_API_TOKEN", "")  # token/chave da sua API
SHOPEE_AFFILIATE_BASE = os.environ.get("SHOPEE_AFFILIATE_BASE", "")  # opcional para construir link
SHOPEE_CHANNEL_ID_ENV = os.environ.get("SHOPEE_CHANNEL_ID")  # canal destino para posts automáticos
DEFAULT_POST_INTERVAL_MIN = int(os.environ.get("SHOPEE_POST_INTERVAL_MIN", "180"))  # padrão: 3h
AUTO_START = os.environ.get("SHOPEE_AUTO_START", "false").lower() == "true"

# Filtros de produto (palavras-chave e categorias)
DEFAULT_KEYWORDS = [
    "gamer","gabinete","gabinetes","placa de video","placa de vídeo","gpu",
    "mousepad","mouse","teclado","mecanico","mecânico","headset","headphone",
    "placa mae","placa mãe","processador","cpu","monitor","cadeira gamer",
    "rgb","setup","decoracao","decoração","led","luminaria","luminária",
    "suporte","mesa gamer","mesa pc","cooler","water cooler","fan",
]
SHOPEE_KEYWORDS = [k.strip().lower() for k in os.environ.get("SHOPEE_KEYWORDS", ",".join(DEFAULT_KEYWORDS)).split(",") if k.strip()]
SHOPEE_CATEGORY_IDS = [p.strip() for p in os.environ.get("SHOPEE_CATEGORY_IDS", "").split(",") if p.strip()]

# Função que recebe mensagens no privado e repassa para o grupo
async def repassar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Só repassa se a mensagem vier do chat privado
    if update.effective_chat.type == "private":
        # Verifica se é o usuário autorizado
        if update.message.from_user.id != USUARIO_AUTORIZADO:
            await update.message.reply_text("Você não tem permissão para usar este bot.")
            return

        # Caso tenha texto
        if update.message.text:
            await context.bot.send_message(chat_id=GRUPO_ID, text=update.message.text)

        # Caso tenha foto
        elif update.message.photo:
            caption = update.message.caption or ""
            file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(chat_id=GRUPO_ID, photo=file_id, caption=caption)

        # Caso tenha vídeo
        elif update.message.video:
            caption = update.message.caption or ""
            file_id = update.message.video.file_id
            await context.bot.send_video(chat_id=GRUPO_ID, video=file_id, caption=caption)

        # Caso tenha documento
        elif update.message.document:
            caption = update.message.caption or ""
            file_id = update.message.document.file_id
            await context.bot.send_document(chat_id=GRUPO_ID, document=file_id, caption=caption)

        # Caso tenha áudio (voz ou música)
        elif update.message.audio:
            caption = update.message.caption or ""
            file_id = update.message.audio.file_id
            await context.bot.send_audio(chat_id=GRUPO_ID, audio=file_id, caption=caption)

        elif update.message.voice:
            file_id = update.message.voice.file_id
            await context.bot.send_voice(chat_id=GRUPO_ID, voice=file_id)

        # Caso tenha sticker
        elif update.message.sticker:
            file_id = update.message.sticker.file_id
            await context.bot.send_sticker(chat_id=GRUPO_ID, sticker=file_id)

        else:
            await update.message.reply_text("Tipo de mensagem não suportado (ainda).")

        await update.message.reply_text("Mensagem enviada ao grupo!")


# =========================
# Utilidades para copiar posts
# =========================

def parse_channel_link_or_args(arg_text: str):
    """Extrai (from_chat_id_or_username, message_id) de um link t.me ou de '@canal msg_id'.
    Retorna (source, msg_id) ou (None, None) se inválido.
    """
    if not arg_text:
        return None, None

    arg_text = arg_text.strip()

    # Formatos aceitos:
    # - https://t.me/<username>/<msg_id>
    # - t.me/<username>/<msg_id>
    m = re.search(r"(?:https?://)?t\.me/(?:c/)?([A-Za-z0-9_]+)/([0-9]+)", arg_text)
    if m:
        return m.group(1), int(m.group(2))

    # - @canal <msg_id>
    parts = arg_text.split()
    if len(parts) == 2 and parts[0].startswith('@') and parts[1].isdigit():
        return parts[0], int(parts[1])

    return None, None


async def copiarpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/copiarpost <link_t.me> ou /copiarpost @canal <msg_id>
    Copia o post indicado para o seu chat.
    """
    if update.effective_chat.type != "private":
        await update.message.reply_text("Use este comando no privado do bot.")
        return

    args_text = " ".join(context.args) if context.args else ""
    source, msg_id = parse_channel_link_or_args(args_text)

    if not source:
        await update.message.reply_text(
            "Envie o link do post (t.me/usuario/ID) ou '@canal ID'.\n"
            "Exemplos:\n"
            "/copiarpost https://t.me/promocoes/123\n"
            "/copiarpost @promocoes 123\n\n"
            "Dica: você também pode me encaminhar um post do canal que eu formato pra você."
        )
        return

    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=source,
            message_id=msg_id,
        )
    except Exception as e:
        await update.message.reply_text(
            "Não consegui copiar o post. Verifique se o canal é público ou se o bot está no canal e o ID está correto."
        )


async def formatar_post_encaminhado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se o usuário encaminhar um post de canal, formata e devolve texto + mídia.
    """
    msg = update.message
    if not msg or not (msg.forward_from_chat or msg.is_automatic_forward):
        return

    # Monta descrição
    descricao = msg.caption or msg.text or ""

    # Heurística simples de preço
    preco_match = re.search(r"R\$\s?\d+[\.,]?\d*", descricao)
    preco = preco_match.group(0) if preco_match else "(ajuste o preço)"

    texto_formatado = (
        "Produto:\n"
        f"{descricao}\n\n"
        f"Preço: {preco}\n"
        "Link de afiliado: <cole o seu aqui>\n"
    )

    # Envia mídia + texto
    if msg.photo:
        file_id = msg.photo[-1].file_id
        await context.bot.send_photo(chat_id=msg.chat_id, photo=file_id, caption=texto_formatado)
    elif msg.video:
        file_id = msg.video.file_id
        await context.bot.send_video(chat_id=msg.chat_id, video=file_id, caption=texto_formatado)
    elif msg.document:
        file_id = msg.document.file_id
        await context.bot.send_document(chat_id=msg.chat_id, document=file_id, caption=texto_formatado)
    else:
        await context.bot.send_message(chat_id=msg.chat_id, text=texto_formatado)


# =========================
# Shopee: busca e postagem automática
# =========================

async def fetch_shopee_products(session: ClientSession) -> List[Dict[str, Any]]:
    """Busca produtos na API da Shopee Afiliados.
    Espera um JSON com uma lista de produtos. Adapte às respostas reais da sua API.
    Cada produto idealmente possui: id, name, description, price, discount, image_url, affiliate_url (opcional).
    """
    if not SHOPEE_API_URL or not SHOPEE_API_TOKEN:
        return []
    headers = {
        "Authorization": f"Bearer {SHOPEE_API_TOKEN}",
        "Accept": "application/json",
    }
    params = {}
    if SHOPEE_CATEGORY_IDS:
        # Muitas APIs aceitam algo como category_ids=1,2,3 — ajuste conforme sua API
        params["category_ids"] = ",".join(SHOPEE_CATEGORY_IDS)

    try:
        async with session.get(SHOPEE_API_URL, headers=headers, params=params or None, timeout=30) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            # Adapte aqui se a estrutura for diferente
            if isinstance(data, dict) and "items" in data:
                return data.get("items", [])
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def normalize_text(s: str) -> str:
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()


def product_matches_keywords(product: Dict[str, Any]) -> bool:
    name = product.get("name") or product.get("title") or ""
    description = product.get("description") or ""
    category = product.get("category") or product.get("category_name") or ""
    blob = f"{name}\n{description}\n{category}"
    blob_n = normalize_text(blob)
    for kw in SHOPEE_KEYWORDS:
        kw_n = normalize_text(kw)
        if kw_n and kw_n in blob_n:
            return True
    return False


def build_affiliate_link(product: Dict[str, Any]) -> Optional[str]:
    if product.get("affiliate_url"):
        return product["affiliate_url"]
    if SHOPEE_AFFILIATE_BASE and product.get("id"):
        return f"{SHOPEE_AFFILIATE_BASE}{product['id']}"
    return None


def format_product_caption(product: Dict[str, Any]) -> str:
    name = product.get("name") or product.get("title") or "Produto"
    description = product.get("description") or ""
    price = product.get("price") or product.get("price_text") or "(ver preço)"
    discount = product.get("discount") or product.get("discount_text") or None
    affiliate = build_affiliate_link(product) or "<cole seu link de afiliado aqui>"

    linhas = [f"{name}"]
    if description:
        linhas.append(description)
    linhas.append("")
    linhas.append(f"Preço: {price}")
    if discount:
        linhas.append(f"Desconto: {discount}")
    linhas.append(f"Link: {affiliate}")
    return "\n".join(linhas)


async def post_random_shopee_product(context: ContextTypes.DEFAULT_TYPE):
    app = context.application
    bot_data = app.bot_data
    channel_id = bot_data.get("shopee_channel_id")
    if not channel_id:
        # fallback: usa env se setado
        channel_id = int(SHOPEE_CHANNEL_ID_ENV) if SHOPEE_CHANNEL_ID_ENV else None
    if not channel_id:
        return

    async with ClientSession() as session:
        products = await fetch_shopee_products(session)
        if not products:
            return
        filtered = [p for p in products if product_matches_keywords(p)]
        pool = filtered if filtered else products  # fallback se filtro ficar vazio
        product = random.choice(pool)

        caption = format_product_caption(product)
        image_url = product.get("image_url") or product.get("image")

        try:
            if image_url:
                await context.bot.send_photo(chat_id=channel_id, photo=image_url, caption=caption)
            else:
                await context.bot.send_message(chat_id=channel_id, text=caption)
        except Exception:
            # ignora erro de envio para manter o job vivo
            pass


# Comandos de controle
async def shopee_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_user.id != USUARIO_AUTORIZADO:
        await update.message.reply_text("Sem permissão.")
        return
    interval_min = context.application.bot_data.get("shopee_interval_min", DEFAULT_POST_INTERVAL_MIN)
    job_queue = context.application.job_queue
    # Cancela job anterior se existir
    for job in job_queue.get_jobs_by_name("shopee_auto_post"):
        job.schedule_removal()
    job_queue.run_repeating(post_random_shopee_product, interval=interval_min * 60, first=5, name="shopee_auto_post")
    await update.message.reply_text(f"Shopee auto-post ON. Intervalo: {interval_min} min")


async def shopee_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_user.id != USUARIO_AUTORIZADO:
        await update.message.reply_text("Sem permissão.")
        return
    job_queue = context.application.job_queue
    removed = False
    for job in job_queue.get_jobs_by_name("shopee_auto_post"):
        job.schedule_removal()
        removed = True
    await update.message.reply_text("Shopee auto-post OFF" if removed else "Já estava desligado.")


async def shopee_set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_user.id != USUARIO_AUTORIZADO:
        await update.message.reply_text("Sem permissão.")
        return
    if not context.args:
        await update.message.reply_text("Use: /shopee_channel <ID do canal>")
        return
    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Canal inválido. Envie um número (ex: -1001234567890)")
        return
    context.application.bot_data["shopee_channel_id"] = channel_id
    await update.message.reply_text(f"Canal configurado: {channel_id}")


async def shopee_set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_user.id != USUARIO_AUTORIZADO:
        await update.message.reply_text("Sem permissão.")
        return
    if not context.args:
        await update.message.reply_text("Use: /shopee_interval <minutos>")
        return
    try:
        minutes = int(context.args[0])
        if minutes < 5:
            await update.message.reply_text("Mínimo 5 minutos para evitar bloqueios.")
            return
    except ValueError:
        await update.message.reply_text("Envie um número inteiro de minutos.")
        return
    context.application.bot_data["shopee_interval_min"] = minutes
    await update.message.reply_text(f"Intervalo configurado: {minutes} min")

async def health_check(request):
    """Endpoint simples para o Render verificar que o serviço está rodando"""
    return web.Response(text="Bot está rodando!")

async def create_http_server():
    """Cria um servidor HTTP simples na porta PORT para satisfazer o Render"""
    app_http = web.Application()
    app_http.router.add_get("/", health_check)
    
    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app_http)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Servidor HTTP rodando na porta {port}")

async def main():
    # Cria servidor HTTP em background para o Render
    await create_http_server()
    
    # Inicia o bot do Telegram
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("copiarpost", copiarpost))
    # Shopee controls
    app.add_handler(CommandHandler("shopee_on", shopee_on))
    app.add_handler(CommandHandler("shopee_off", shopee_off))
    app.add_handler(CommandHandler("shopee_channel", shopee_set_channel))
    app.add_handler(CommandHandler("shopee_interval", shopee_set_interval))
    app.add_handler(MessageHandler(filters.FORWARDED & (~filters.ChatType.GROUPS), formatar_post_encaminhado))
    app.add_handler(MessageHandler(filters.ALL, repassar))

    # Inicializa o bot de forma assíncrona
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Auto start (opcional via env)
    if AUTO_START:
        # Intervalo default ou configurado em env já está em DEFAULT_POST_INTERVAL_MIN
        job_queue = app.job_queue
        for job in job_queue.get_jobs_by_name("shopee_auto_post"):
            job.schedule_removal()
        job_queue.run_repeating(post_random_shopee_product, interval=DEFAULT_POST_INTERVAL_MIN * 60, first=5, name="shopee_auto_post")
    
    print("✅ Bot está rodando e pronto para repassar mensagens (texto, imagem, vídeo, etc)...")
    
    # Mantém o bot rodando
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
