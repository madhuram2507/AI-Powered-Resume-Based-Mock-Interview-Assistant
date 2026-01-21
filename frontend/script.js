let mediaRecorder;
let audioChunks = [];
let audioBlob = null;
let streamRef = null;

const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const submitBtn = document.getElementById("submitBtn");
const statusText = document.getElementById("status");

startBtn.onclick = async () => {
  try {
    streamRef = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(streamRef);

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

    mediaRecorder.onstop = () => {
      audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      audioChunks = [];
      submitBtn.disabled = false;
      statusText.innerText = "Recording complete. Ready to submit.";

      // 🔴 Stop mic stream properly
      streamRef.getTracks().forEach(track => track.stop());
    };

    mediaRecorder.start();
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusText.innerText = "Recording...";
  } catch (err) {
    alert("Microphone access denied");
  }
};

stopBtn.onclick = () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
};

submitBtn.onclick = async () => {
  if (!audioBlob) return;

  statusText.innerText = "Evaluating answer...";
  submitBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", audioBlob, "answer.wav");

  const questionId = 1;

  try {
    const response = await fetch(
      `http://127.0.0.1:8000/interview/answer/${questionId}`,
      {
        method: "POST",
        body: formData
      }
    );

    if (!response.ok) {
      throw new Error("Backend error");
    }

    const data = await response.json();
    console.log("Backend response:", data);

    document.getElementById("score").innerText = data.score ?? "N/A";
    document.getElementById("transcript").innerText = data.answer ?? "";
    document.getElementById("feedback").innerText = data.feedback ?? "";
    document.getElementById("improved").innerText =
      "Improved answer will be added in Phase-5D";

    document.getElementById("result").classList.remove("hidden");
    statusText.innerText = "Evaluation complete.";
  } catch (error) {
    statusText.innerText = "Error while evaluating answer.";
    console.error(error);
  }
};
