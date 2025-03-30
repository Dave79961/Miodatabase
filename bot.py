Typhon

import os
import pymongo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, Filters, CallbackContext
from urllib.parse import urlparse

# Stati della conversazione per aggiungere un link
CATEGORY, CUSTOM_CATEGORY, LINK = range(3)

# Connessione a MongoDB
try:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI non è definito nelle variabili d'ambiente")
    mongo_client = pymongo.MongoClient(mongo_uri)
    db = mongo_client["Miodatabase"]
    links_collection = db["links"]
except Exception as e:
    print(f"Errore nella connessione a MongoDB: {e}")
    raise

# Categorie predefinite
PREDEFINED_CATEGORIES = ["Tecnologia", "Crypto", "Giochi", "Social", "Notizie"]

# Funzione per inviare il menu con i pulsanti
def send_menu(update: Update, context: CallbackContext) -> None:
    try:
        keyboard = [
            [InlineKeyboardButton("Aggiungi Link", callback_data='add_link')],
            [InlineKeyboardButton("Ottieni Link", callback_data='get_link')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            update.message.reply_text('Scegli un’opzione:', reply_markup=reply_markup)
        elif update.callback_query and update.callback_query.message:
            update.callback_query.message.reply_text('Scegli un’opzione:', reply_markup=reply_markup)
        else:
            print("Errore: nessun messaggio disponibile per inviare il menu.")
    except Exception as e:
        print(f"Errore in send_menu: {e}")

# Comando /start con pulsanti
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    update.message.reply_text('Benvenuto! Scegli un’opzione:')
    send_menu(update, context)

# Funzione per avviare la conversazione di aggiunta link e mostrare le categorie
def start_add_link(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query:
        query.answer()

    keyboard = [[InlineKeyboardButton(category, callback_data=f'cat_{category}')] for category in PREDEFINED_CATEGORIES]
    keyboard.append([InlineKeyboardButton("Altra categoria", callback_data='cat_custom')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.message.reply_text('Scegli una categoria per il link:', reply_markup=reply_markup)
    else:
        update.message.reply_text('Scegli una categoria per il link:', reply_markup=reply_markup)
    return CATEGORY

# Gestione dei pulsanti
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data == 'get_link':
        try:
            categories = list(set(link['category'] for link in links_collection.find()))
            print(f"Categorie trovate: {categories}")
            if not categories:
                query.message.reply_text('Nessun link disponibile.')
                send_menu(update, context)
                return

            keyboard = [[InlineKeyboardButton(category, callback_data=f'category_{category}')] for category in categories]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.message.reply_text('Scegli una categoria:', reply_markup=reply_markup)
        except Exception as e:
            print(f"Errore in get_link: {e}")
            query.message.reply_text('Si è verificato un errore. Riprova.')
            send_menu(update, context)
    elif query.data.startswith('category_'):
        try:
            category = query.data.replace('category_', '')
            category_links = [link['link'] for link in links_collection.find({'category': category})]
            print(f"Link nella categoria {category}: {category_links}")
            if category_links:
                import random
                selected_link = random.choice(category_links)
                query.message.reply_text(f'Ecco un link dalla categoria {category}: {selected_link}')
            else:
                query.message.reply_text(f'Nessun link disponibile nella categoria {category}.')
            send_menu(update, context)
        except Exception as e:
            print(f"Errore in category selection: {e}")
            query.message.reply_text('Si è verificato un errore. Riprova.')
            send_menu(update, context)
    elif query.data.startswith('cat_'):
        if query.data == 'cat_custom':
            query.message.reply_text('Inserisci il nome della categoria personalizzata:')
            return CUSTOM_CATEGORY
        else:
            category = query.data.replace('cat_', '')
            context.user_data['category'] = category
            query.message.reply_text(f'Hai scelto la categoria "{category}". Ora inserisci il link (es. https://example.com):')
            return LINK

# Gestione della categoria personalizzata
def custom_category(update: Update, context: CallbackContext) -> int:
    category = update.message.text.strip()
    context.user_data['category'] = category
    update.message.reply_text(f'Hai scelto la categoria "{category}". Ora inserisci il link (es. https://example.com):')
    return LINK

# Passo: Ricevi il link
def link(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    link = update.message.text.strip()
    category = context.user_data.get('category')

    if link.startswith('t.me/'):
        link = 'https://' + link
    elif not (link.startswith('http://') or link.startswith('https://')):
        update.message.reply_text('Inserisci un link valido (es. https://example.com o t.me/nomebot).')
        send_menu(update, context)
        return ConversationHandler.END

    try:
        result = urlparse(link)
        if not all([result.scheme, result.netloc]):
            update.message.reply_text('Inserisci un link valido (es. https://example.com o t.me/nomebot).')
            send_menu(update, context)
            return ConversationHandler.END
    except ValueError:
        update.message.reply_text('Inserisci un link valido (es. https://example.com o t.me/nomebot).')
        send_menu(update, context)
        return ConversationHandler.END

    try:
        links_collection.insert_one({'user_id': user_id, 'link': link, 'category': category})
        update.message.reply_text(f'Link aggiunto nella categoria {category}!')
        send_menu(update, context)
    except Exception as e:
        print(f"Errore durante il salvataggio del link: {e}")
        update.message.reply_text('Si è verificato un errore durante il salvataggio del link. Riprova.')
        send_menu(update, context)

    return ConversationHandler.END

# Gestione della cancellazione della conversazione
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Azione annullata.')
    send_menu(update, context)
    return ConversationHandler.END

# Avvio del bot
def main() -> None:
    # Leggi il token dalle variabili d'ambiente
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN non è definito nelle variabili d'ambiente")

    # Inizializza l'Updater
    updater = Updater(bot_token, use_context=True)
    dispatcher = updater.dispatcher

    # Aggiungi i gestori
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button, pattern='^(get_link|category_.*|cat_.*)$'))

    # Configura il ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("addlink", start_add_link),
            CallbackQueryHandler(start_add_link, pattern='^add_link$')
        ],
        states={
            CATEGORY: [CallbackQueryHandler(button, pattern='^cat_.*$')],
            CUSTOM_CATEGORY: [MessageHandler(Filters.text & ~Filters.command, custom_category)],
            LINK: [MessageHandler(Filters.text & ~Filters.command, link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(conv_handler)

    # Avvia il bot
    print("Bot avviato! Vai su Telegram e usa i comandi.")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()