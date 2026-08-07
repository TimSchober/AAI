/**
 * Routes and the side menu are the same list.
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import ChatView from '@/views/ChatView.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'
import ReviewView from '@/views/ReviewView.vue'
import SettingsView from '@/views/SettingsView.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** Menu entry text; entries without a label stay out of the menu. */
    label?: string
    hint?: string
  }
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'chat',
    component: ChatView,
    meta: { label: 'Chat' },
  },
  {
    path: '/unterlagen',
    name: 'review',
    component: ReviewView,
    meta: { label: 'Unterlagen-Check', hint: 'Lebenslauf hochladen und prüfen lassen' },
  },
  {
    path: '/wissen',
    name: 'knowledge',
    component: KnowledgeView,
    meta: { label: 'Wissensdatenbank', hint: 'Dokumente und gespeicherte Stellen' },
  },
  {
    path: '/einstellungen',
    name: 'settings',
    component: SettingsView,
    meta: { label: 'Einstellungen', hint: 'Modell, Dienste und Limits' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
