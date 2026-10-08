import { createContext, useContext } from 'react'

/** Lets any page open the chat, optionally "about" a product with suggested questions. */
export interface ChatControl {
  openChat: (topic?: { productName: string; questions: string[] }) => void
}

export const ChatControlContext = createContext<ChatControl>({ openChat: () => undefined })

export const useChatControl = () => useContext(ChatControlContext)
