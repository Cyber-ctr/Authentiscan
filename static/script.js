document.addEventListener("DOMContentLoaded", () => {
  const scanButton = document.getElementById("scan-button");
  const reportButton = document.getElementById("report-button");
  const demoButton = document.querySelector(".primary-btn");

  if (demoButton) {
    demoButton.addEventListener("click", () => {
      document.getElementById("scanner").scrollIntoView({
        behavior: "smooth",
      });
    });
  }

  if (scanButton) {
    scanButton.addEventListener("click", scan);
  }

  if (reportButton) {
    reportButton.addEventListener("click", downloadReport);
  }
});

async function scan() {
  const textInput = document.getElementById("text");
  const fileInput = document.getElementById("fileInput");
  const loading = document.getElementById("loading");
  const button = document.getElementById("scan-button");
  const resultDiv = document.getElementById("result");

  loading.style.display = "block";
  button.disabled = true;
  resultDiv.innerHTML = "";

  try {
    let response;

    if (fileInput.files.length > 0) {
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);

      response = await fetch("/upload", {
        method: "POST",
        body: formData,
      });
    } else {
      const text = textInput.value.trim();

      if (!text) {
        throw new Error("Please provide text or upload a document.");
      }

      response = await fetch("/scan", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Scan failed.");
    }

    let html = `
      <div class="result-card low">
        <h2>Overall Similarity: ${data.overall_similarity}%</h2>
        <p>${data.sentence_count} sentence(s) analyzed.</p>
      </div>
    `;

    data.details.forEach((d) => {
      const cls = d.final_score >= 75 ? "high" : d.final_score >= 40 ? "med" : "low";
      html += `
        <div class="result-card ${cls}">
          <p>${d.sentence}</p>
          <div class="score-row">
            AI: ${d.ai_score}% | Web: ${d.web_score}% | Final: ${d.final_score}%
          </div>
        </div>
      `;
    });

    html += `
      <div class="result-card low">
        <h3>Detected Web Sources</h3>
        ${
          data.web_sources.length
            ? data.web_sources.map((w) => `<p>🔗 ${w}</p>`).join("")
            : "<p>No web sources detected.</p>"
        }
      </div>
    `;

    resultDiv.innerHTML = html;
    document.getElementById("report-button").style.display = "block";
  } catch (error) {
    resultDiv.innerHTML = `
      <div class="result-card high">
        <p>${error.message}</p>
      </div>
    `;
  } finally {
    loading.style.display = "none";
    button.disabled = false;
  }
}

async function downloadReport() {
  const text = document.getElementById("text").value.trim();

  if (!text) {
    alert("Please enter text first.");
    return;
  }

  try {
    const response = await fetch("/generate-report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      throw new Error("Failed to generate report.");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = "Authentiscan_Report.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (error) {
    alert(error.message);
  }
}
