"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SidebarProvider = void 0;
const vscode = require("vscode");
class SidebarProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };
        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        webviewView.webview.onDidReceiveMessage((data) => __awaiter(this, void 0, void 0, function* () {
            switch (data.type) {
                case "onInfo": {
                    if (!data.value) {
                        return;
                    }
                    vscode.window.showInformationMessage(data.value);
                    break;
                }
                case "onError": {
                    if (!data.value) {
                        return;
                    }
                    vscode.window.showErrorMessage(data.value);
                    break;
                }
                case "askAgent": {
                    const text = data.value;
                    // Send to our FastAPI backend
                    try {
                        // Using global fetch (available in modern VS Code Node environments)
                        // or we could use axios if it was in package.json
                        const response = yield fetch("http://localhost:8000/generate/agent", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                question: text,
                                language: "yaml" // Hardcoded as requested for first test
                            })
                        });
                        if (!response.ok) {
                            throw new Error(`API returned ${response.status}`);
                        }
                        const result = yield response.json();
                        // Send back to webview
                        webviewView.webview.postMessage({
                            type: "agentResponse",
                            value: result.generated_code,
                            iterations: result.iteration_count
                        });
                    }
                    catch (err) {
                        vscode.window.showErrorMessage("Failed to connect to GKN RAG Core: " + err.message);
                        webviewView.webview.postMessage({
                            type: "agentError",
                            value: err.message
                        });
                    }
                    break;
                }
            }
        }));
    }
    revive(panel) {
        this._view = panel;
    }
    _getHtmlForWebview(webview) {
        const styleResetUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, "media", "reset.css"));
        const styleVSCodeUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, "media", "vscode.css"));
        const nonce = getNonce();
        return `<!DOCTYPE html>
			<html lang="en">
			<head>
				<meta charset="UTF-8">
				<meta name="viewport" content="width=device-width, initial-scale=1.0">
				<title>GKN AI Sidebar</title>
                <style>
                    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 10px; }
                    #chat { height: 70vh; overflow-y: auto; border-bottom: 1px solid #333; margin-bottom: 10px; padding-bottom: 10px; }
                    .msg { margin-bottom: 15px; }
                    .user { font-weight: bold; color: var(--vscode-textLink-foreground); }
                    .agent { color: var(--vscode-debugConsole-infoForeground); }
                    .code { background: #1e1e1e; padding: 10px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; font-size: 11px; margin-top: 5px; border: 1px solid #444; }
                    textarea { width: 100%; height: 60px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 3px; resize: none; }
                    button { width: 100%; padding: 8px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; cursor: pointer; margin-top: 5px; }
                    button:hover { background: var(--vscode-button-hoverBackground); }
                    .status { font-size: 10px; opacity: 0.7; margin-top: 3px; }
                </style>
			</head>
			<body>
				<div id="chat">
                    <div class="msg agent">Hello! I am the GKN AI Assistant. Ask me to generate configurations or analyze infrastructure.</div>
                </div>
				<textarea id="input" placeholder="Ask a question..."></textarea>
				<button id="send">Send to Agent</button>

				<script nonce="${nonce}">
					const vscode = acquireVsCodeApi();
                    const chatDiv = document.getElementById('chat');
                    const inputArea = document.getElementById('input');
                    const sendBtn = document.getElementById('send');

                    sendBtn.addEventListener('click', () => {
                        const text = inputArea.value;
                        if (!text) return;
                        
                        // Add user message to UI
                        const userDiv = document.createElement('div');
                        userDiv.className = 'msg';
                        userDiv.innerHTML = '<span class="user">User:</span> ' + text;
                        chatDiv.appendChild(userDiv);
                        
                        // Clear input
                        inputArea.value = '';
                        
                        // Send to Extension Host
                        vscode.postMessage({ type: 'askAgent', value: text });
                        
                        // Simple placeholder for agent
                        const loadingDiv = document.createElement('div');
                        loadingDiv.className = 'msg agent';
                        loadingDiv.id = 'loading';
                        loadingDiv.innerText = 'Agent is thinking...';
                        chatDiv.appendChild(loadingDiv);
                        chatDiv.scrollTop = chatDiv.scrollHeight;
                    });

                    window.addEventListener('message', event => {
                        const message = event.data;
                        const loading = document.getElementById('loading');
                        if (loading) loading.remove();

                        switch (message.type) {
                            case 'agentResponse': {
                                const agentDiv = document.createElement('div');
                                agentDiv.className = 'msg agent';
                                agentDiv.innerHTML = '<span class="user">Agent:</span> (Iterations: ' + message.iterations + ')<div class="code">' + escapeHtml(message.value) + '</div>';
                                chatDiv.appendChild(agentDiv);
                                break;
                            }
                            case 'agentError': {
                                const errDiv = document.createElement('div');
                                errDiv.className = 'msg agent';
                                errDiv.style.color = 'red';
                                errDiv.innerText = 'Error: ' + message.value;
                                chatDiv.appendChild(errDiv);
                                break;
                            }
                        }
                        chatDiv.scrollTop = chatDiv.scrollHeight;
                    });

                    function escapeHtml(text) {
                        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
                    }
				</script>
			</body>
			</html>`;
    }
}
exports.SidebarProvider = SidebarProvider;
function getNonce() {
    let text = "";
    const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
//# sourceMappingURL=SidebarProvider.js.map