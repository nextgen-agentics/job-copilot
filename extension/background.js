/**
 * background.js — Service Worker
 * Opens the side panel when the extension icon is clicked.
 * Relays messages between content.js (page context) and sidepanel.js.
 */

// Open side panel on icon click
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

// Relay page context from content.js → sidepanel.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "PAGE_CONTEXT") {
    // Store page context so sidepanel can retrieve it
    chrome.storage.session.set({ pageContext: message.data }, () => {
      sendResponse({ ok: true });
    });
    return true; // async
  }
});
