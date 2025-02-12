import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import dotenv from "dotenv";
import Groq from "groq-sdk";  // Import Groq SDK

dotenv.config();

const app = express();
const PORT = 5000;

app.use(cors());
app.use(bodyParser.json());

// Initialize Groq API
const groq = new Groq({
    apiKey: process.env.GROQ_API_KEY, // Ensure you have set this in your .env file
});

app.post("/api/answer_question", async (req, res) => {
    try {
        const { question, history } = req.body;
        console.log("User Question:", question);
        console.log("Conversation History:", history);

        // Construct chat history for Groq API
        const messages = [
            ...Object.values(history).map(({ query, response }) => (
                [{ role: "user", content: query }, { role: "assistant", content: response }]
            )).flat(),
            { role: "user", content: question }
        ];

        console.log("Formatted Messages:", messages);

        // API call to Groq
        const completion = await groq.chat.completions.create({
            model: "llama3-70b-8192",  // Specify the Groq model (adjust based on your need)
            messages,
        });

        console.log("Groq API Response:", completion);

        if (!completion.choices || completion.choices.length === 0) {
            throw new Error("No choices returned from Groq API");
        }

        res.json({ result: completion.choices[0].message.content });
    } catch (error) {
        console.error("Error fetching response:", error);
        res.status(500).json({ result: "⚠️ Error: Could not fetch response. Please try again later." });
    }
});

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
