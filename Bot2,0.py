import pymongo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from urllib.parse import urlparse

# Stati della conversazione per aggiungere un link
CATEGORY, CUSTOM_CATEGORY, LINK = range(3)

# Connessione a MongoDB
try:
    mongo_client = pymongo.MongoClient("mongodb+srv://valag79:Figlio221503?@cluster0.mongodb.net/Miodatabase?retryWrites=true&w=majority")
    db = mongo_client["Miodatabase"]
    links_collection = db["links"]
except Exception as e:
    print(f"Errore nella connessione a MongoDB: {e}")
    raise

# Categorie predefinite
PREDEFINED_CATEGORIES = ["Tecnologia", "Crypto", "Giochi", "Social", "Notizie"]

# Funzione per inviare il menu con i pulsanti
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        keyboard = [
            [InlineKeyboardButton("Aggiungi Link", callback_data='add_link')],
            [InlineKeyboardButton("Ottieni Link", callback_data='get_link')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text('Scegli un’opzione:', reply_markup=reply_markup)
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text('Scegli un’opzione:', reply_markup=reply_markup)
        else:
            print("Errore: nessun messaggio disponibile per inviare il menu.")
    except Exception as e:
        print(f"Errore in send_menu: {e}")

# Comando /start con pulsanti
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    await update.message.reply_text('Benvenuto! Scegli un’opzione:')
    await send_menu(update, context)

# Funzione per avviare la conversazione di aggiunta link e mostrare le categorie
async def start_add_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [[InlineKeyboardButton(category, callback_data=f'cat_{category}')] for category in PREDEFINED_CATEGORIES]
    keyboard.append([InlineKeyboardButton("Altra categoria", callback_data='cat_custom')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.message.reply_text('Scegli una categoria per il link:', reply_markup=reply_markup)
    else:
        await update.message.reply_text('Scegli una categoria per il link:', reply_markup=reply_markup)
    return CATEGORY

# Gestione dei pulsanti
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'get_link':
        try:
            categories = list(set(link['category'] for link in links_collection.find()))
            print(f"Categorie trovate: {categories}")
            if not categories:
                await query.message.reply_text('Nessun link disponibile.')
                await send_menu(update, context)
                return

            keyboard = [[InlineKeyboardButton(category, callback_data=f'category_{category}')] for category in categories]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text('Scegli una categoria:', reply_markup=reply_markup)
        except Exception as e:
            print(f"Errore in get_link: {e}")
            await query.message.reply_text('Si è verificato un errore. Riprova.')
            await send_menu(update, context)
    elif query.data.startswith('category_'):
        try:
            category = query.data.replace('category_', '')
            category_links = [link['link'] for link in links_collection.find({'category': category})]
            print(f"Link nella categoria {category}: {category_links}")
            if category_links:
                import random
                selected_link = random.choice(category_links)
                await query.message.reply_text(f'Ecco un link dalla categoria {category}: {selected_link}')
            else:
                await query.message.reply_text(f'Nessun link disponibile nella categoria {category}.')
            await send_menu(update, context)
        except Exception as e:
            print(f"Errore in category selection: {e}")
            await query.message.reply_text('Si è verificato un errore. Riprova.')
            await send_menu(update, context)
    elif query.data.startswith('cat_'):
        if query.data == 'cat_custom':
            await query.message.reply_text('Inserisci il nome della categoria personalizzata:')
            return CUSTOM_CATEGORY
        else:
            category = query.data.replace('cat_', '')
            context.user_data['category'] = category
            await query.message.reply_text(f'Hai scelto la categoria "{category}". Ora inserisci il link (es. https://example.com):')
            return LINK

# Gestione della categoria personalizzata
async def custom_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text.strip()
    context.user_data['category'] = category
    await update.message.reply_text(f'Hai scelto la categoria "{category}". Ora inserisci il link (es. https://example.com):')
    return LINK

# Passo: Ricevi il link
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    link = update.message.text.strip()
    category = context.user_data.get('category')

    if link.startswith('t.me/'):
        link = 'https://' + link
    elif not (link.startswith('http://') or link.startswith('https://')):
        await update.message.reply_text('Inserisci un link valido (es. https://example.com o t.me/nomebot).')
        await send_menu(update, context)
        return ConversationHandler.END

    try:
        result = urlparse(link)
        if not all([result.scheme, result.netloc]):
            await update.message.reply_text('Inserisci un link valido (es. https://example.com o t.me/nomebot).')
            await send_menu(update, context)
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text('Inserisci un link valido (es. https://example.com o t.me/nomebot).')
        await send_menu(update, context)
        return ConversationHandler.END

    try:
        links_collection.insert_one({'user_id': user_id, 'link': link, 'category': category})
        await update.message.reply_text(f'Link aggiunto nella categoria {category}!')
        await send_menu(update, context)
    except Exception as e:
        print(f"Errore durante il salvataggio del link: {e}")
        await update.message.reply_text('Si è verificato un errore durante il salvataggio del link. Riprova.')
        await send_menu(update, context)

    return ConversationHandler.END

# Gestione della cancellazione della conversazione
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Azione annullata.')
    await send_menu(update, context)
    return ConversationHandler.END

# Avvio del bot
def main() -> None:
    application = Application.builder().token("8142992227:AAFRtDg4lEn5LpktEftMa6Aeuqk8loDRxZM").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button, pattern='^(get_link|category_.*|cat_.*)$'))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("addlink", start_add_link),
            CallbackQueryHandler(start_add_link, pattern='^add_link$')
        ],
        states={
            CATEGORY: [CallbackQueryHandler(button, pattern='^cat_.*$')],
            CUSTOM_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_category)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)

    print("Bot avviato! Vai su Telegram e usa i comandi.")
    application.run_polling()

if __name__ == '__main__':
    main()