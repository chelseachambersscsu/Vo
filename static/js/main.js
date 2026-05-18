/* ===================================================================
   MemoBoat — main.js  (Home page interactions)
   =================================================================== */

document.addEventListener("DOMContentLoaded", function () {
  const meetingType = document.getElementById("meetingType");
  const rawNotes = document.getElementById("rawNotes");
  const btnClear = document.getElementById("btnClear");
  const btnGenerate = document.getElementById("btnGenerate");

  const placeholder = document.getElementById("previewPlaceholder");
  const loading = document.getElementById("previewLoading");
  const result = document.getElementById("previewResult");
  const errorBox = document.getElementById("previewError");

  const memoSummary = document.getElementById("memoSummary");
  const memoActions = document.getElementById("memoActions");
  const memoDecisions = document.getElementById("memoDecisions");

  // ---- Helpers --------------------------------------------------------
  function showPanel(panel) {
    [placeholder, loading, result, errorBox].forEach(function (el) {
      el.classList.add("d-none");
    });
    panel.classList.remove("d-none");
  }

  // ---- Clear button ---------------------------------------------------
  btnClear.addEventListener("click", function () {
    meetingType.selectedIndex = 0;
    rawNotes.value = "";
    showPanel(placeholder);
  });

  // ---- Generate button ------------------------------------------------
  btnGenerate.addEventListener("click", function () {
    var typeId = meetingType.value;
    var notes = rawNotes.value.trim();

    if (!typeId) {
      alert("Please select a meeting type.");
      return;
    }
    if (!notes) {
      alert("Please enter your meeting notes.");
      return;
    }

    showPanel(loading);
    btnGenerate.disabled = true;

    fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type_id: typeId, raw_notes: notes }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (resp) {
        btnGenerate.disabled = false;

        if (!resp.ok) {
          errorBox.textContent = resp.data.error || "Something went wrong.";
          showPanel(errorBox);
          return;
        }

        // Summary
        memoSummary.textContent = resp.data.summary;

        // Action items (checkboxes)
        memoActions.innerHTML = "";
        (resp.data.action_items || []).forEach(function (item, idx) {
          var li = document.createElement("li");
          li.className = "form-check mb-2";
          li.innerHTML =
            '<input class="form-check-input" type="checkbox" id="ai' +
            idx +
            '">' +
            '<label class="form-check-label" for="ai' +
            idx +
            '">' +
            escapeHtml(item) +
            "</label>";
          memoActions.appendChild(li);
        });

        // Key decisions (bullets)
        memoDecisions.innerHTML = "";
        (resp.data.key_decisions || []).forEach(function (dec) {
          var li = document.createElement("li");
          li.className = "mb-1";
          li.textContent = dec;
          memoDecisions.appendChild(li);
        });

        showPanel(result);
      })
      .catch(function (err) {
        btnGenerate.disabled = false;
        errorBox.textContent = "Network error: " + err.message;
        showPanel(errorBox);
      });
  });

  // ---- XSS helper -----------------------------------------------------
  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
});
