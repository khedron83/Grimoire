import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

document.addEventListener("contextmenu", e => e.preventDefault());

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
