from telegram.ext import Updater, CommandHandler, Filters, ChatMemberHandler
import random
from telegram.error import Unauthorized

ADMINS = {1705618342, 1361096971}  # <-- Replace with your admin Telegram user ID(s)
pairing_pool = {}     # {chat_id: [(user_id, full_name)]}
numbered_map = {}     # {chat_id: [(number, name)]}
left_users = {}       # {chat_id: set((user_id, full_name))}
skipped_users = {}    # {chat_id: set((user_id, full_name))}

def join(update, context):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in pairing_pool:
        pairing_pool[chat_id] = []
    if chat_id not in left_users:
        left_users[chat_id] = set()
    if chat_id not in skipped_users:
        skipped_users[chat_id] = set()
    # Can't join if skipped already for this round
    if (user.id, user.full_name) in skipped_users[chat_id]:
        update.message.reply_text("You have chosen to skip this round. Use /skip again to undo and then /join to participate.")
        return
    if (user.id, user.full_name) not in pairing_pool[chat_id]:
        pairing_pool[chat_id].append((user.id, user.full_name))
        left_users[chat_id].discard((user.id, user.full_name))
        update.message.reply_text(f"✅ {user.full_name}, you've joined the next pairing round!")
    else:
        update.message.reply_text("You have already joined.")

def leave(update, context):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in left_users:
        left_users[chat_id] = set()
    if (user.id, user.full_name) in pairing_pool.get(chat_id, []):
        pairing_pool[chat_id].remove((user.id, user.full_name))
        left_users[chat_id].add((user.id, user.full_name))
        update.message.reply_text("❌ You have left the pairing round.")
    else:
        update.message.reply_text("You were not in the current pairing pool.")

def skip(update, context):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in skipped_users:
        skipped_users[chat_id] = set()
    if (user.id, user.full_name) in skipped_users[chat_id]:
        # Unskip: Remove from skip list, now eligible to join again
        skipped_users[chat_id].remove((user.id, user.full_name))
        update.message.reply_text("You have removed your skip. Use /join if you want to participate.")
    else:
        # If user is in pool, remove from pool and add to skipped
        if (user.id, user.full_name) in pairing_pool.get(chat_id, []):
            pairing_pool[chat_id].remove((user.id, user.full_name))
        skipped_users[chat_id].add((user.id, user.full_name))
        update.message.reply_text("⏭️ You have skipped this pairing round.")

def list_joined(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        update.message.reply_text("❌ Only admin can view the list.")
        return

    pool = pairing_pool.get(chat_id, [])
    leavers = left_users.get(chat_id, set())
    skippers = skipped_users.get(chat_id, set())

    if not pool and not leavers and not skippers:
        update.message.reply_text("No one has joined yet.")
        return

    msg = "📋 *List of Joined Users and Their Random Numbers:*\n"
    numbered = []
    if pool:
        num_users = len(pool)
        unique_numbers = random.sample(range(100, 1000), num_users)
        numbered = list(zip(unique_numbers, [name for (_, name) in pool]))
        numbered.sort()
        numbered_map[chat_id] = numbered
        for num, name in numbered:
            msg += f"{num}: {name}\n"
    else:
        msg += "No users currently joined.\n"

    if leavers:
        msg += "\n🚪 *Users who left this round:*\n"
        for _, name in leavers:
            msg += f"- {name}\n"
    if skippers:
        msg += "\n⏭️ *Users who skipped this round:*\n"
        for _, name in skippers:
            msg += f"- {name}\n"

    try:
        context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
        update.message.reply_text("📋 List sent to your private chat!")
    except Unauthorized:
        update.message.reply_text(
            "❗ Bot cannot message you privately. Please start the bot in DM first, then try again."
        )

def pair_by_number(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        update.message.reply_text("❌ Only admin can pair users.")
        return
    numbered = numbered_map.get(chat_id)
    if not numbered or len(numbered) < 2:
        update.message.reply_text("Not enough users or run /list first.")
        return
    numbers_only = [num for num, _ in numbered]
    random.shuffle(numbers_only)
    pairs = []
    for i in range(0, len(numbers_only) - 1, 2):
        pairs.append((numbers_only[i], numbers_only[i+1]))
    leftover = numbers_only[-1] if len(numbers_only) % 2 == 1 else None
    result = "🎲 *Book Pairings (by Random Number):*\n"
    for a, b in pairs:
        result += f"• {a} ↔️ {b}\n"
    if leftover:
        result += f"\nNot paired this time: {leftover}"
    update.message.reply_text(result, parse_mode="Markdown")
    pairing_pool[chat_id] = []
    numbered_map[chat_id] = []
    left_users[chat_id] = set()
    skipped_users[chat_id] = set()

def welcome_new_member(update, context):
    new_status = update.chat_member.new_chat_member.status
    old_status = update.chat_member.old_chat_member.status
    user = update.chat_member.new_chat_member.user
    # Welcome only if the user just joined (wasn't a member before)
    if old_status not in ["member", "administrator", "creator"] and new_status == "member":
        context.bot.send_message(
            chat_id=update.chat_member.chat.id,
            text=(
                f"👋 Welcome, {user.full_name}!\n\n"
                "Here’s how you can participate in the book exchange:\n"
                "• /join – Join the next book exchange round\n"
                "• /leave – Leave the current round if you change your mind\n"
                "• /skip – Skip this round (toggle: use again to undo skip)\n\n"
                "When enough people join, the admin will pair users for book swaps. Enjoy! 📚"
            )
        )

def start(update, context):
    update.message.reply_text(
        "👋 Welcome! Send /join to enter the book exchange, /leave to quit, /skip to skip this round (or /skip again to undo)."
    )

def main():
    TOKEN = '8123095363:AAGSy7z89za86dJWdOyk0nGnrDgmEI70IOw'  # <-- Place your bot token here
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("join", join, filters=Filters.chat_type.groups))
    dp.add_handler(CommandHandler("leave", leave, filters=Filters.chat_type.groups))
    dp.add_handler(CommandHandler("skip", skip, filters=Filters.chat_type.groups))
    dp.add_handler(CommandHandler("list", list_joined, filters=Filters.chat_type.groups))
    dp.add_handler(CommandHandler("pair", pair_by_number, filters=Filters.chat_type.groups))
    dp.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
