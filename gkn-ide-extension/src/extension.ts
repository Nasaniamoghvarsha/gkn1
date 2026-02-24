import * as vscode from 'vscode';
import { SidebarProvider } from './SidebarProvider';

export function activate(context: vscode.ExtensionContext) {
    const sidebarProvider = new SidebarProvider(context.extensionUri);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            "gkn.aiSidebar",
            sidebarProvider
        )
    );

    context.subscriptions.push(
        vscode.commands.registerCommand("gkn-ai-assistant.helloWorld", () => {
            vscode.window.showInformationMessage("Hello from GKN AI Assistant!");
        })
    );
}

export function deactivate() { }
