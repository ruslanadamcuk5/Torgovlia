declare const __APP_VERSION__: string
declare const __APP_BUILD__: string

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

interface Window {
  __deferredInstallPrompt?: BeforeInstallPromptEvent
}
