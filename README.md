
# WhatsApp School Chatbot

Lets parents check their kid's attendance, marks, and school events on WhatsApp — no app, no login, just the number they already message on. Built this for a real K-10 school with 600+ students. This repo is the cleaned-up demo version — real code, fake sample data, no actual student info or API keys.

## The interesting bits

Most of the hard part wasn't the AI, it was the data:

- Names alone aren't unique (lots of overlapping first names), so matching runs on name + mobile number together
- No roll numbers existed, so the bot auto-generates a student ID the first time someone shows up in a sheet
- Marks are stored per subject per exam (`FA1-MATHS`, `FA1-ENGLISH`...) instead of one combined score, since that's actually what parents ask about
- The school just resends the same sheet every exam cycle — the sync script figures out which exam it is from the column headers and updates records on its own
- If someone asks something outside its scope (like parenting advice), it doesn't improvise — it points to an actual source and stops there

## Stack

Python/FastAPI backend, Node/Express for the WhatsApp side, Supabase for the DB, Groq for the LLM calls, deployed on Render.

## Running it

\`\`\`bash
pip install -r requirements.txt
cp .env.example .env   # add your own Supabase/Groq/WhatsApp keys
python main.py
\`\`\`

\`\`\`bash
cd whatsapp-bot
npm install
cp .env.example .env
node server.js
\`\`\`

\`sample_students.csv\` has 3 fake students in the right format if you want to test the matching/sync logic yourself.

---

2nd-year CSE (AI/ML) student — happy to talk through any of the decisions if you're building something similar.
