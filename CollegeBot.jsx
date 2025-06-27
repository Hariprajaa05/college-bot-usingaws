import React, { useState, useEffect } from "react";

function CollegeBot() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [department, setDepartment] = useState("CSE");
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // ✅ Load from localStorage initially
  const [history, setHistory] = useState(() => {
    const saved = localStorage.getItem("collegeBotHistory");
    return saved ? JSON.parse(saved) : [];
  });

  const [selectedQA, setSelectedQA] = useState(() => {
    const saved = localStorage.getItem("collegeBotSelectedQA");
    return saved ? JSON.parse(saved) : null;
  });

  // ✅ Save to localStorage on changes
  useEffect(() => {
    localStorage.setItem("collegeBotHistory", JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    if (selectedQA) {
      localStorage.setItem("collegeBotSelectedQA", JSON.stringify(selectedQA));
    }
  }, [selectedQA]);

  // ✅ Convert markdown links
  function convertMarkdownLinksToHTML(text) {
    return text.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#33A1FF;">$1</a>'
    );
  }

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    try {
      const response = await fetch(
        `https://l2n698llce.execute-api.us-east-1.amazonaws.com/prod/GetCollegeInfo?q=${encodeURIComponent(
          question
        )}&department=${department.toLowerCase()}`
      );

      const data = await response.json();
      const responseAnswer = data.answer || "No response received.";

      const newQA = { question, answer: responseAnswer };
      setAnswer(responseAnswer);
      setSelectedQA(newQA);
      setHistory((prev) => [...prev, newQA]);
      setQuestion("");
    } catch (error) {
      const errorMsg = "❌ Error: " + error.message;
      const errorQA = { question, answer: errorMsg };
      setAnswer(errorMsg);
      setSelectedQA(errorQA);
      setHistory((prev) => [...prev, errorQA]);
    }
    setLoading(false);
  };

  const handleHistoryClick = (item) => {
    setQuestion(item.question);
    setSelectedQA(item);
    setShowHistory(false);
  };

  const handleDelete = (indexToDelete) => {
    const deleted = history[indexToDelete];
    const updated = history.filter((_, index) => index !== indexToDelete);
    setHistory(updated);

    if (
      selectedQA &&
      selectedQA.question === deleted.question &&
      selectedQA.answer === deleted.answer
    ) {
      setSelectedQA(null);
      localStorage.removeItem("collegeBotSelectedQA");
    }
  };

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* Sidebar */}
      <div
        style={{
          width: "250px",
          backgroundColor: "#1e1e1e",
          color: "#f0f0f0",
          padding: "1rem",
          borderRight: "1px solid #333",
        }}
      >
        <h3 style={{ color: "#33FF99", marginBottom: "1rem" }}>📁 History</h3>
        <button
          onClick={() => setShowHistory(!showHistory)}
          style={{
            width: "100%",
            backgroundColor: "#2b2b2b",
            color: "#fff",
            padding: "0.75rem",
            fontSize: "1rem",
            borderRadius: "6px",
            border: "1px solid #444",
            marginBottom: "1rem",
            cursor: "pointer",
          }}
        >
          {showHistory ? "Hide" : "Show"} Questions
        </button>

        {showHistory && (
          <div style={{ maxHeight: "70vh", overflowY: "auto" }}>
            {history.map((item, index) => (
              <div
                key={index}
                style={{
                  marginBottom: "1rem",
                  padding: "0.5rem",
                  backgroundColor: "#2a2a2a",
                  borderRadius: "6px",
                }}
              >
                <div
                  onClick={() => handleHistoryClick(item)}
                  style={{
                    cursor: "pointer",
                    marginBottom: "0.5rem",
                    fontSize: "0.9rem",
                    color: "#33A1FF",
                  }}
                >
                  {item.question.length > 40
                    ? item.question.slice(0, 40) + "..."
                    : item.question}
                </div>
                <button
                  onClick={() => handleDelete(index)}
                  style={{
                    background: "transparent",
                    color: "#FF6B6B",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                  }}
                >
                  ❌ Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main Chat Panel */}
      <div
        style={{
          flex: 1,
          backgroundColor: "#121212",
          color: "#f0f0f0",
          padding: "2rem",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          overflowY: "auto",
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
            style={{
              fontSize: "1.8rem",
              marginBottom: "1rem",
              color: "#33FF99",
            }}
          >
            🎓 College Info AI Bot
          </h2>

          {/* Department Dropdown */}
          <label
            style={{
              display: "block",
              marginBottom: "0.5rem",
              color: "#ccc",
              fontSize: "1rem",
            }}
          >
            Select Department:
          </label>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            style={{
              width: "100%",
              padding: "0.75rem",
              fontSize: "1rem",
              borderRadius: "8px",
              border: "1px solid #333",
              backgroundColor: "#2b2b2b",
              color: "#fff",
              marginBottom: "1rem",
              outline: "none",
            }}
          >
            <option value="CSE">CSE</option>
            <option value="IT">IT</option>
            <option value="CSBS">CSBS</option>
            <option value="AIDS">AIDS</option>
          </select>

          <input
            type="text"
            placeholder={`Ask something about ${department}...`}
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

          {selectedQA && (
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
              <div
                style={{ marginTop: "0.5rem" }}
                dangerouslySetInnerHTML={{
                  __html: convertMarkdownLinksToHTML(selectedQA.answer),
                }}
              ></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default CollegeBot;
