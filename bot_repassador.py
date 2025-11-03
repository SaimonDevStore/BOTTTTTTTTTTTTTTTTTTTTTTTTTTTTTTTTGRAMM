import os
import re
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# CONFIGURAÇÕES
TOKEN = "8378547653:AAF25X5RDPbivxqLRvQSzYrVTn4seqpqDVI"  # token do seu bot
GRUPO_ID = -1003236154348  # ID do grupo
USUARIO_AUTORIZADO = 5782277642  # seu ID

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
    app.add_handler(MessageHandler(filters.FORWARDED & (~filters.ChatType.GROUPS), formatar_post_encaminhado))
    app.add_handler(MessageHandler(filters.ALL, repassar))
    
    # Inicializa o bot de forma assíncrona
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    print("✅ Bot está rodando e pronto para repassar mensagens (texto, imagem, vídeo, etc)...")
    
    # Mantém o bot rodando
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
