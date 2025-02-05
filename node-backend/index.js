import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import OpenAI from "openai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 5000;

app.use(cors());
app.use(bodyParser.json());

const openai = new OpenAI({
    baseURL: "https://openrouter.ai/api/v1",
    apiKey: process.env.OPENROUTER_API_KEY,
    defaultHeaders: {
        "HTTP-Referer": process.env.SITE_URL || "http://localhost:3000", 
        "X-Title": process.env.SITE_NAME || "HR Tech",
    },
});

app.post("/api/answer_question", async (req, res) => {
    try {
      const { question, history } = req.body;
      console.log(question);
      console.log(history);
        const messages = [
            ...Object.values(history).map(({ query, response }) => (
                [{ role: "user", content: query }, { role: "assistant", content: response }]
            )).flat(),
            { role: "user", content: question }
        ];
        console.log(messages);
        const completion = await openai.chat.completions.create({
          model: "openai/gpt-4o",
          messages
      });
      
      console.log('Completion:', completion);  // Log the entire completion object
      
      if (!completion.choices || completion.choices.length === 0) {
          throw new Error('No choices returned from API');
      }
      
      res.json({ result: completion.choices[0].message.content });
  } catch (error) {
      console.error("Error fetching response:", error);
      console.error("Error details:", JSON.stringify(error, null, 2));  // Log detailed error information
      res.status(500).json({ result: "⚠️ Error: Could not fetch response. Please try again later." });
  }
});

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
