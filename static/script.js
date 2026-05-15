/* =========================
   AUTHENTISCAN FRONTEND
========================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {

    initializeApp();

  }
);

/* =========================
   INITIALIZATION
========================= */

function initializeApp(){

  const scanButton =
    document.getElementById(
      "scan-button"
    );

  const reportButton =
    document.getElementById(
      "report-button"
    );

  const demoButton =
    document.querySelector(
      ".primary-btn"
    );

  /* -------------------------
     HERO BUTTON
  ------------------------- */

  if(demoButton){

    demoButton.addEventListener(
      "click",
      () => {

        document
          .getElementById(
            "scanner"
          )
          .scrollIntoView({
            behavior:"smooth"
          });

      }
    );

  }

  /* -------------------------
     SCAN BUTTON
  ------------------------- */

  if(scanButton){

    scanButton.addEventListener(
      "click",
      scan
    );

  }

  /* -------------------------
     REPORT BUTTON
  ------------------------- */

  if(reportButton){

    reportButton.addEventListener(
      "click",
      downloadReport
    );

  }

}

/* =========================
   HTML ESCAPE SECURITY
========================= */

function escapeHTML(str){

  if(!str) return "";

  return str
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#039;");

}

/* =========================
   SCAN FUNCTION
========================= */

async function scan(){

  const textInput =
    document.getElementById(
      "text"
    );

  const fileInput =
    document.getElementById(
      "fileInput"
    );

  const loading =
    document.getElementById(
      "loading"
    );

  const button =
    document.getElementById(
      "scan-button"
    );

  const resultDiv =
    document.getElementById(
      "result"
    );

  /* -------------------------
     UI STATE
  ------------------------- */

  loading.style.display = "block";

  button.disabled = true;

  resultDiv.innerHTML = "";

  try{

    let response;

    /* -------------------------
       FILE UPLOAD SCAN
    ------------------------- */

    if(fileInput.files.length > 0){

      const file =
        fileInput.files[0];

      /* FILE VALIDATION */

      const allowedTypes = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
      ];

      const maxSize =
        5 * 1024 * 1024;

      if(
        !allowedTypes.includes(file.type)
      ){

        throw new Error(
          "Unsupported file type."
        );

      }

      if(file.size > maxSize){

        throw new Error(
          "File exceeds 5MB limit."
        );

      }

      const formData =
        new FormData();

      formData.append(
        "file",
        file
      );

      response = await fetch(
        "/upload",
        {
          method:"POST",
          body:formData
        }
      );

    }

    /* -------------------------
       TEXT SCAN
    ------------------------- */

    else{

      const text =
        textInput.value.trim();

      if(!text){

        throw new Error(
          "Please provide text or upload a document."
        );

      }

      if(text.length < 10){

        throw new Error(
          "Text is too short."
        );

      }

      response = await fetch(
        "/scan",
        {
          method:"POST",

          headers:{
            "Content-Type":
              "application/json"
          },

          body:JSON.stringify({
            text
          })
        }
      );

    }

    /* -------------------------
       RESPONSE
    ------------------------- */

    const data =
      await response.json();

    if(!response.ok){

      throw new Error(
        data.detail ||
        "Scan failed."
      );

    }

    renderResults(data);

    document.getElementById(
      "report-button"
    ).style.display = "block";

  }

  catch(error){

    resultDiv.innerHTML = `

      <div class="result-card high">

        <h3>
          Scan Error
        </h3>

        <p>
          ${escapeHTML(error.message)}
        </p>

      </div>

    `;

  }

  finally{

    loading.style.display = "none";

    button.disabled = false;

  }

}

/* =========================
   RENDER RESULTS
========================= */

function renderResults(data){

  const resultDiv =
    document.getElementById(
      "result"
    );

  let html = `

    <div class="result-card low">

      <h2>
        Overall Similarity:
        ${data.overall_similarity}%
      </h2>

      <p>
        ${data.sentence_count}
        sentence(s) analyzed.
      </p>

    </div>

  `;

  /* -------------------------
     SENTENCE RESULTS
  ------------------------- */

  data.details.forEach((d) => {

    const cls =
      d.final_score >= 75
      ? "high"
      : d.final_score >= 40
      ? "med"
      : "low";

    html += `

      <div class="result-card ${cls}">

        <p>
          ${escapeHTML(d.sentence)}
        </p>

        <div class="score-row">

          AI:
          ${d.ai_score}% |

          Web:
          ${d.web_score}% |

          Final:
          ${d.final_score}%

        </div>

      </div>

    `;

  });

  /* -------------------------
     WEB SOURCES
  ------------------------- */

  html += `

    <div class="result-card low">

      <h3>
        Detected Web Sources
      </h3>

      ${
        data.web_sources.length

        ? data.web_sources
          .map(
            (w) => `

              <p>
                🔗 ${escapeHTML(w)}
              </p>

            `
          )
          .join("")

        : `
            <p>
              No web sources detected.
            </p>
          `
      }

    </div>

  `;

  resultDiv.innerHTML = html;

}

/* =========================
   PDF REPORT DOWNLOAD
========================= */

async function downloadReport(){

  const text =
    document.getElementById(
      "text"
    ).value.trim();

  if(!text){

    alert(
      "Please enter text first."
    );

    return;

  }

  try{

    const response =
      await fetch(
        "/generate-report",
        {
          method:"POST",

          headers:{
            "Content-Type":
              "application/json"
          },

          body:JSON.stringify({
            text
          })
        }
      );

    if(!response.ok){

      throw new Error(
        "Failed to generate report."
      );

    }

    const blob =
      await response.blob();

    const url =
      window.URL.createObjectURL(
        blob
      );

    const a =
      document.createElement(
        "a"
      );

    a.href = url;

    a.download =
      "Authentiscan_Report.pdf";

    document.body.appendChild(a);

    a.click();

    a.remove();

    window.URL.revokeObjectURL(
      url
    );

  }

  catch(error){

    alert(
      escapeHTML(
        error.message
      )
    );

  }

}