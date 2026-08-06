/**
 * Routes and the side menu are the same list.
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import ChatView from '@/views/ChatView.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'

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
    path: '/wissen',
    name: 'knowledge',
    component: PlaceholderView,
    meta: { label: 'Wissensdatenbank', hint: 'Dokumente und gespeicherte Stellen' },
  },
  {
    path: '/einstellungen',
    name: 'settings',
    component: PlaceholderView,
    meta: { label: 'Einstellungen', hint: 'Modell, Agent und Präferenzen' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
