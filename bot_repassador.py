from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

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

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Captura todos os tipos de mensagem
    app.add_handler(MessageHandler(filters.ALL, repassar))

    print("✅ Bot está rodando e pronto para repassar mensagens (texto, imagem, vídeo, etc)...")
    app.run_polling()

if __name__ == "__main__":
    main()
