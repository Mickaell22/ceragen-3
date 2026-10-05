import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Un solo .env en la raíz del monorepo. Vite solo expone las variables VITE_*.
  envDir: '..',
});
