import React, { useState } from "react";

function CollegeBot() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    try {
      const response = await fetch(
        `https://l2n698llce.execute-api.us-east-1.amazonaws.com/prod/GetCollegeInfo?q=${encodeURIComponent(
          question
        )}`
      );
      const data = await response.json();
      setAnswer(data.answer || "No response received.");
    } catch (error) {
      setAnswer("❌ Error: " + error.message);
    }
    setLoading(false);
  };

  return (
    <div
      style={{
        height: "100vh",
        backgroundColor: "#121212",
        color: "#f0f0f0",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Inter, sans-serif",
        padding: "2rem",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "700px",
          backgroundColor: "#1e1e1e",
          padding: "2rem",
          borderRadius: "12px",
          boxShadow: "0 0 30px rgba(0,0,0,0.4)",
        }}
      >
        <h2
          style={{ fontSize: "1.8rem", marginBottom: "1rem", color: "#33FF99" }}
        >
          🎓 College Info AI Bot
        </h2>

        <input
          type="text"
          placeholder="Ask something about B.E CSE..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          style={{
            width: "100%",
            padding: "0.9rem 1rem",
            fontSize: "1rem",
            borderRadius: "8px",
            border: "1px solid #333",
            backgroundColor: "#2b2b2b",
            color: "#fff",
            marginBottom: "1rem",
            outline: "none",
          }}
        />

        <button
          onClick={handleAsk}
          style={{
            backgroundColor: "#33FF99",
            color: "#000",
            padding: "0.75rem 1.5rem",
            fontSize: "1rem",
            borderRadius: "8px",
            border: "none",
            cursor: "pointer",
            fontWeight: "bold",
            transition: "background 0.2s ease",
          }}
        >
          {loading ? "Thinking..." : "Ask"}
        </button>

        {answer && (
          <div
            style={{
              marginTop: "2rem",
              backgroundColor: "#2a2a2a",
              padding: "1rem 1.25rem",
              borderRadius: "10px",
              lineHeight: "1.6",
              maxHeight: "300px",
              overflowY: "auto",
              whiteSpace: "pre-wrap",
            }}
          >
            <strong style={{ color: "#33FF99" }}>Answer:</strong>
            <p style={{ marginTop: "0.5rem" }}>{answer}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default CollegeBot;
