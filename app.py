import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, CallbackContext
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import re
from fuzzywuzzy import process


# print("it works!")

load_dotenv()

# Configuration
os.environ["SUPABASE_URL"] = os.getenv("SUPABASE_URL")
os.environ["SUPABASE_KEY"] = os.getenv("SUPABASE_KEY")
os.environ["TELEGRAM_TOKEN"] = os.getenv("TELEGRAM_TOKEN")


# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# if Client:
#     print(Client)

# Initialize Telegram Bot
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
print(TELEGRAM_TOKEN)


ASK_ALIAS, SELECT_BUSINESS, SELECT_BUSINESS_CHOICE, GET_RATING, GET_REVIEW = range(
    5)


async def handle_unexpected_input(update: Update, context: CallbackContext):
    # Send a friendly message and remind the user to start with /start
    await update.message.reply_text(
        "Hi! To get started, please use /start."
    )


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome! Please enter your name")
    return ASK_ALIAS


async def ask_alias(update: Update, context: CallbackContext):
    user_alias = update.message.text
    context.user_data["user_alias"] = user_alias
    await update.message.reply_text("Please enter the name of the business you'd like to review.")
    return SELECT_BUSINESS


async def select_business(update: Update, context: CallbackContext):
    business_name = update.message.text
    response = supabase.table("businesses").select(
        "id", "business_name").execute()
    all_businesses = response.data

    business_names = [b["business_name"] for b in all_businesses]
    matches = process.extract(business_name, business_names, limit=3)

    if matches:
        options_text = "\n".join(
            [f"{i+1}. {match[0]}" for i, match in enumerate(matches)])
        await update.message.reply_text(
            f"Did you mean:\n{options_text}\n\nPlease reply with the number of your choice."
        )

        context.user_data["matches"] = {str(
            i+1): all_businesses[business_names.index(match[0])]["id"] for i, match in enumerate(matches)}
        return SELECT_BUSINESS_CHOICE
    else:
        await update.message.reply_text("No matching businesses found. Please try again.")
        return SELECT_BUSINESS


async def handle_business_choice(update: Update, context: CallbackContext):
    choice = update.message.text
    selected_business_id = context.user_data["matches"].get(choice)

    if selected_business_id:
        context.user_data["business_id"] = selected_business_id
        await update.message.reply_text("Great! Please give a rating from 1 to 5.")
        return GET_RATING
    else:
        await update.message.reply_text("Invalid choice. Please try again by typing the correct number.")
        return SELECT_BUSINESS_CHOICE


async def get_rating(update: Update, context: CallbackContext):
    try:
        rating = int(update.message.text)
        if 1 <= rating <= 5:
            context.user_data["rating"] = rating
            await update.message.reply_text("Thank you! Please write your review text.")
            return GET_REVIEW
        else:
            await update.message.reply_text("Rating must be between 1 and 5. Please try again.")
            return GET_RATING
    except ValueError:
        await update.message.reply_text("Invalid rating. Please enter a number between 1 and 5.")
        return GET_RATING


async def get_review(update: Update, context: CallbackContext):
    review_text = update.message.text
    user_id = update.message.from_user.id
    business_id = context.user_data["business_id"]
    rating = context.user_data["rating"]
    user_alias = context.user_data["user_alias"]

    # Insert review into Supabase
    supabase.table("reviews").insert({
        "user": str(user_id),
        "business_id": business_id,
        "rating": rating,
        "review_text": review_text,
        "user_alias": user_alias
    }).execute()

    await update.message.reply_text("Your review has been submitted. Thank you!")
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Review canceled.")
    return ConversationHandler.END


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    unexpected_input_handler = MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_unexpected_input)
    application.add_handler(unexpected_input_handler)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_ALIAS: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, ask_alias)],
            SELECT_BUSINESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_business)],
            SELECT_BUSINESS_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_business_choice)],
            GET_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rating)],
            GET_REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_review)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
