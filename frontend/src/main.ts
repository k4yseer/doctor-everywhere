import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './style.css';

import PrimeVue from 'primevue/config';
import Aura from '@primeuix/themes/aura';
import router from './router';

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(PrimeVue, {
    theme: {
        preset: Aura,
        options: {
            cssLayer: { name: 'primevue', order: 'theme, base, primevue' },
            darkModeSelector: '.p-dark',
        }
    }
});

app.mount('#app');
