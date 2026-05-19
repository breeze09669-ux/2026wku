const payload = {
  contents: [{ parts: [{ text: "hello" }] }],
  tools: [{ googleSearch: {} }],
  generationConfig: {
    responseMimeType: "application/json"
  }
};
fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=invalid", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
}).then(async r => {
  console.log(r.status);
  console.log(await r.text());
});
