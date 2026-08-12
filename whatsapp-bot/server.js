const express = require("express");
require("dotenv").config();

const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3000;

const VERIFY_TOKEN =
  process.env.VERIFY_TOKEN ||
  process.env.WEBHOOK_SECRET ||
  "my_custom_webhook_secret_123";

// ======================================================
// GET /webhook
// Meta Verification
// ======================================================

app.get("/webhook", (req, res) => {
  console.log("\n==============================");
  console.log("🔍 WEBHOOK VERIFICATION");
  console.log("==============================");

  console.log("Query:", req.query);

  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    console.log("✅ Verification Successful");
    return res.status(200).send(challenge);
  }

  console.log("❌ Verification Failed");
  return res.sendStatus(403);
});

// ======================================================
// POST /webhook
// Receives WhatsApp Events
// ======================================================

app.post("/webhook", (req, res) => {
  console.log("\n========================================");
  console.log("📨 NEW WEBHOOK EVENT");
  console.log("Time:", new Date().toISOString());
  console.log("========================================");

  console.log("Headers:");
  console.log(req.headers);

  console.log("\nBody:");
  console.log(JSON.stringify(req.body, null, 2));

  const body = req.body;

  if (body.object !== "whatsapp_business_account") {
    console.log("❌ Not a WhatsApp webhook");
    return res.sendStatus(404);
  }

  const value =
    body.entry?.[0]?.changes?.[0]?.value;

  if (value?.messages?.length) {
    const msg = value.messages[0];

    console.log("\n========== MESSAGE ==========");
    console.log("From :", msg.from);
    console.log("Type :", msg.type);

    if (msg.type === "text") {
      console.log("Text :", msg.text.body);
    }

    console.log("=============================");
  }

  if (value?.statuses?.length) {
    console.log("\n========== STATUS ==========");

    value.statuses.forEach((status) => {
      console.log(status.status);
    });

    console.log("============================");
  }

  res.sendStatus(200);
});

// ======================================================

app.listen(PORT, () => {
  console.log("\n========================================");
  console.log("🚀 WhatsApp Webhook Running");
  console.log("Port :", PORT);
  console.log("Verify Token :", VERIFY_TOKEN);
  console.log("========================================\n");
});