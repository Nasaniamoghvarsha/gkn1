"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = require("vscode");
const SidebarProvider_1 = require("./SidebarProvider");
function activate(context) {
    const sidebarProvider = new SidebarProvider_1.SidebarProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider("gkn.aiSidebar", sidebarProvider));
    context.subscriptions.push(vscode.commands.registerCommand("gkn-ai-assistant.helloWorld", () => {
        vscode.window.showInformationMessage("Hello from GKN AI Assistant!");
    }));
}
exports.activate = activate;
function deactivate() { }
exports.deactivate = deactivate;
//# sourceMappingURL=extension.js.map