import { defineAsyncComponent } from 'vue'

export const dialogs = {
  products: defineAsyncComponent(() => import('./ProductsDialog.vue')),
  payment: defineAsyncComponent(() => import('./PaymentDialog.vue')),
}
