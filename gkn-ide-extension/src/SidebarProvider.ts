import * as vscode from 'vscode';

export class SidebarProvider implements vscode.WebviewViewProvider {
    _view?: vscode.WebviewView;
    _doc?: vscode.TextDocument;

    constructor(private readonly _extensionUri: vscode.Uri) { }

    public resolveWebviewView(webviewView: vscode.WebviewView) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (data) => {
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
                    try {
                        // Use 127.0.0.1 explicitly to avoid Windows IPv6 localhost resolution issues
                        const response = await fetch("http://127.0.0.1:8001/generate/agent", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                question: text,
                                language: "yaml"
                            })
                        });

                        if (!response.ok) {
                            const errorText = await response.text();
                            throw new Error(`API Error: ${response.status} - ${errorText}`);
                        }

                        const result: any = await response.json();

                        // Send back to webview as 'addResponse'
                        this._view?.webview.postMessage({
                            type: "addResponse",
                            value: result.generated_code,
                            iterations: result.iteration_count
                        });

                    } catch (err: any) {
                        const msg = err.message || "Unknown error";
                        vscode.window.showErrorMessage("GKN RAG Core Error: " + msg);
                        this._view?.webview.postMessage({
                            type: "addResponse",
                            error: true,
                            value: "Connectivity Error: " + msg + ". Ensure the backend is running on port 8001."
                        });
                    }
                    break;
                }
            }
        });
    }

    public revive(panel: vscode.WebviewView) {
        this._view = panel;
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const nonce = getNonce();

        return `<!DOCTYPE html>
			<html lang="en">
			<head>
				<meta charset="UTF-8">
				<meta name="viewport" content="width=device-width, initial-scale=1.0">
				<title>GKN AI Sidebar</title>
                <style>
                    body { 
                        font-family: var(--vscode-font-family); 
                        color: var(--vscode-foreground); 
                        padding: 10px; 
                        display: flex;
                        flex-direction: column;
                        height: 100vh;
                        box-sizing: border-box;
                    }
                    #chat { 
                        flex: 1;
                        overflow-y: auto; 
                        border-bottom: 1px solid var(--vscode-panel-border); 
                        margin-bottom: 10px; 
                        padding-bottom: 10px; 
                        display: flex;
                        flex-direction: column;
                        gap: 15px;
                    }
                    .msg { 
                        padding: 8px;
                        border-radius: 4px;
                    }
                    .user-msg { 
                        background: var(--vscode-textBlockQuote-background);
                        align-self: flex-end;
                        border-left: 3px solid var(--vscode-textLink-foreground);
                        width: 90%;
                    }
                    .agent-msg { 
                        background: var(--vscode-sideBar-background);
                        align-self: flex-start;
                        border-left: 3px solid var(--vscode-debugConsole-infoForeground);
                        width: 95%;
                    }
                    .user-label { font-weight: bold; color: var(--vscode-textLink-foreground); display: block; margin-bottom: 4px; }
                    .agent-label { font-weight: bold; color: var(--vscode-debugConsole-infoForeground); display: block; margin-bottom: 4px; }
                    
                    .code-block { 
                        background: #1e1e1e; 
                        padding: 12px; 
                        border-radius: 6px; 
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace; 
                        white-space: pre-wrap; 
                        font-size: 12px; 
                        margin-top: 8px; 
                        border: 1px solid #333;
                        color: #d4d4d4;
                        line-height: 1.4;
                        overflow-x: auto;
                    }
                    textarea { 
                        width: 100%; 
                        height: 80px; 
                        background: var(--vscode-input-background); 
                        color: var(--vscode-input-foreground); 
                        border: 1px solid var(--vscode-input-border); 
                        border-radius: 4px; 
                        resize: none; 
                        padding: 8px;
                        font-family: inherit;
                    }
                    button { 
                        width: 100%; 
                        padding: 10px; 
                        background: var(--vscode-button-background); 
                        color: var(--vscode-button-foreground); 
                        border: none; 
                        cursor: pointer; 
                        margin-top: 8px; 
                        font-weight: bold;
                        border-radius: 2px;
                    }
                    button:hover { background: var(--vscode-button-hoverBackground); }
                    .loading { font-style: italic; opacity: 0.6; font-size: 11px; }
                    .error { color: var(--vscode-errorForeground); }
                </style>
			</head>
			<body>
				<div id="chat">
                    <div class="msg agent-msg">
                        <span class="agent-label">GKN AI Assistant</span>
                        Hello! I am ready to generate configurations or analyze your infrastructure. What can I help you with today?
                    </div>
                </div>
				<textarea id="input" placeholder="Ask a question..."></textarea>
				<button id="send">Send to Agent</button>

				<script nonce="${nonce}">
					const vscode = acquireVsCodeApi();
                    const chatDiv = document.getElementById('chat');
                    const inputArea = document.getElementById('input');
                    const sendBtn = document.getElementById('send');

                    function addMessage(type, text, isCode = false, iterations = null) {
                        const msgDiv = document.createElement('div');
                        msgDiv.className = 'msg ' + (type === 'user' ? 'user-msg' : 'agent-msg');
                        
                        const label = document.createElement('span');
                        label.className = type === 'user' ? 'user-label' : 'agent-label';
                        label.innerText = type === 'user' ? 'User' : 'Agent' + (iterations ? ' (System Corrected in ' + iterations + ' iterations)' : '');
                        msgDiv.appendChild(label);

                        if (isCode) {
                            const codePre = document.createElement('div');
                            codePre.className = 'code-block';
                            codePre.innerText = text;
                            msgDiv.appendChild(codePre);
                        } else {
                            const textSpan = document.createElement('span');
                            textSpan.innerText = text;
                            msgDiv.appendChild(textSpan);
                        }

                        chatDiv.appendChild(msgDiv);
                        chatDiv.scrollTop = chatDiv.scrollHeight;
                    }

                    sendBtn.addEventListener('click', () => {
                        const text = inputArea.value.trim();
                        if (!text) return;
                        
                        addMessage('user', text);
                        inputArea.value = '';
                        
                        vscode.postMessage({ type: 'askAgent', value: text });
                        
                        const loadingDiv = document.createElement('div');
                        loadingDiv.className = 'msg agent-msg loading';
                        loadingDiv.id = 'loading-indicator';
                        loadingDiv.innerText = 'Agent is analyzing and validating output...';
                        chatDiv.appendChild(loadingDiv);
                        chatDiv.scrollTop = chatDiv.scrollHeight;
                    });

                    // Listen for messages from the extension
                    window.addEventListener('message', event => {
                        const message = event.data;
                        const loading = document.getElementById('loading-indicator');
                        if (loading) loading.remove();

                        switch (message.type) {
                            case 'addResponse': {
                                if (message.error) {
                                    addMessage('agent', message.value);
                                    const lastMsg = chatDiv.lastChild;
                                    lastMsg.classList.add('error');
                                } else {
                                    addMessage('agent', message.value, true, message.iterations);
                                }
                                break;
                            }
                        }
                    });
				</script>
			</body>
			</html>`;
    }
}

function getNonce() {
    let text = "";
    const possible =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
