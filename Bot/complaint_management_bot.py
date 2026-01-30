import logging
import os
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========== .env LOADING ============
load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# ADMIN_IDS as list of ints
ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get('ADMIN_IDS', '').split(',')
    if x.strip().isdigit()
]

# =========== LOGGING SETUP ===========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========== PROJECT ROLE DATA ===========
PROJECT_ROLES = [
    {
        "key": "pm",
        "name": "Project Manager & System Analyst",
        "desc": (
            "Responsible for project planning, requirement analysis, system documentation, use-case modeling, "
            "coordination among team members, and ensuring timely project delivery."
        ),
    },
    {
        "key": "backend",
        "name": "Backend Developer",
        "desc": (
            "Responsible for designing backend architecture, implementing REST APIs, handling authentication and "
            "authorization, managing complaint and feedback workflows, and integrating the database."
        ),
    },
    {
        "key": "frontend",
        "name": "Frontend Developer",
        "desc": (
            "Responsible for designing and implementing user interfaces, dashboards for users, officers, and administrators; "
            "ensuring responsiveness, usability, and API integration."
        ),
    },
    {
        "key": "ml",
        "name": "Machine Learning & Automation Engineer",
        "desc": (
            "Responsible for implementing complaint classification, priority prediction, and automatic assignment using NLP "
            "techniques such as sentence transformers, improving system intelligence."
        ),
    },
    {
        "key": "devops",
        "name": "Database, DevOps & Testing Engineer",
        "desc": (
            "Responsible for database schema design, ER diagrams, data integrity, Docker and deployment setup, system testing, "
            "and ensuring reliability and performance."
        ),
    },
]

# ========= IN-MEMORY ROLE ASSIGNMENTS ===========
ASSIGNMENTS = dict()     # {role_key: {user_id, name}}
PENDING_CONFIRM = dict() # {user_id: role_key}

# ========= UTILITY FUNCTIONS ==========

def get_role_by_key(role_key):
    return next((role for role in PROJECT_ROLES if role["key"] == role_key), None)

def get_user_role(user_id):
    for key, v in ASSIGNMENTS.items():
        if v["user_id"] == user_id:
            return key
    return None

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_assignments_text():
    lines = []
    for role in PROJECT_ROLES:
        key = role["key"]
        if key in ASSIGNMENTS:
            user = ASSIGNMENTS[key]
            lines.append(
                f"✅ *{role['name']}*\nAssigned to: [{user['name']}](tg://user?id={user['user_id']})"
            )
        else:
            lines.append(f"🟦 *{role['name']}*\n_(Available)_")
    return "\n\n".join(lines)

def role_selection_keyboard():
    keyboard = []
    for role in PROJECT_ROLES:
        role_key = role["key"]
        if role_key in ASSIGNMENTS:
            user = ASSIGNMENTS[role_key]
            btn_text = f"{role['name']} (Taken by {user['name']})"
            keyboard.append(
                [InlineKeyboardButton(btn_text, callback_data="noop")]
            )
        else:
            keyboard.append(
                [InlineKeyboardButton(role["name"], callback_data=f"select:{role_key}")]
            )
    return InlineKeyboardMarkup(keyboard)

# ============= HANDLERS ================

async def start_or_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Welcome to the Complaint Management & Feedback Platform Group Role Selector!*\n\n"
        "Below are the project roles. Click a role to view its description and claim it.\n\n"
        f"{get_assignments_text()}"
    )
    await (update.message or update.callback_query.message).reply_text(
        text, reply_markup=role_selection_keyboard(), parse_mode="Markdown"
    )

async def roles_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "noop":
        await query.answer("This role is already assigned.", show_alert=True)
        return

    if data.startswith("select:"):
        role_key = data.split(":")[1]
        # Prevent if already locked
        if role_key in ASSIGNMENTS:
            await query.answer("This role is already taken.", show_alert=True)
            return

        # One role per user
        if get_user_role(user.id) is not None:
            await query.answer("You already selected a role!", show_alert=True)
            return

        role = get_role_by_key(role_key)
        if not role:
            await query.answer("Invalid role!", show_alert=True)
            return

        PENDING_CONFIRM[user.id] = role_key

        confirm_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm:{role_key}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"cancel")
                ]
            ]
        )
        text = (
            f"*{role['name']}*\n\n{role['desc']}\n\n"
            "_Do you want to take this role?_"
        )
        await query.edit_message_text(
            text, reply_markup=confirm_keyboard, parse_mode="Markdown"
        )

    elif data.startswith("confirm:"):
        role_key = data.split(":")[1]

        if role_key in ASSIGNMENTS:
            await query.answer("Sorry, this role is already taken!", show_alert=True)
            return

        if get_user_role(user.id) is not None:
            await query.answer("You can select only one role!", show_alert=True)
            return

        ASSIGNMENTS[role_key] = {
            "user_id": user.id,
            "name": user.full_name
        }
        PENDING_CONFIRM.pop(user.id, None)
        text = (
            f"🎉 Congratulations, [{user.full_name}](tg://user?id={user.id})!\n\n"
            f"You are now assigned: *{get_role_by_key(role_key)['name']}*."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "cancel":
        PENDING_CONFIRM.pop(user.id, None)
        await query.edit_message_text(
            "❌ Role selection cancelled. You can pick a role again using /roles.",
            parse_mode="Markdown"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Current Role Assignments:*\n\n" + get_assignments_text(),
        parse_mode="Markdown"
    )

async def myrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_role_key = get_user_role(user_id)
    if user_role_key:
        role = get_role_by_key(user_role_key)
        await update.message.reply_text(
            f"🌟 Your role:\n\n*{role['name']}*\n{role['desc']}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "You haven't selected a role yet! Use /roles to pick one."
        )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ *You are not authorized to reset assignments.*",
            parse_mode="Markdown"
        )
        return
    ASSIGNMENTS.clear()
    PENDING_CONFIRM.clear()
    await update.message.reply_text("🔄 All role assignments have been reset!\nEveryone can select roles again.")

# ============= MAIN BOT APP =============

def main():
    if not BOT_TOKEN:
        raise Exception("Bot token not set! Please provide BOT_TOKEN in .env file.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # For group only commands
    app.add_handler(CommandHandler("start", start_or_roles, filters=filters.ChatType.GROUPS))
    app.add_handler(CommandHandler("roles", start_or_roles, filters=filters.ChatType.GROUPS))
    app.add_handler(CommandHandler("status", status, filters=filters.ChatType.GROUPS))
    app.add_handler(CommandHandler("myrole", myrole, filters=filters.ChatType.GROUPS))
    app.add_handler(CommandHandler("reset", reset, filters=filters.ChatType.GROUPS))
    # So users get a DM welcome, but need to join the group for role picking:
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text(
        "👋 Hi! Please add me to your group and use /roles to pick a project role."
    ), filters=filters.ChatType.PRIVATE))
    # Handles all inline keyboard actions
    app.add_handler(CallbackQueryHandler(roles_callback))

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()