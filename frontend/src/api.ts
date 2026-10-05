// Se incrusta en el build: cambiarla exige recompilar el front.
export const API_URL = import.meta.env.VITE_API_URL;

if (!API_URL) {
  throw new Error('Falta VITE_API_URL: definirla en .env antes de compilar');
}

export type Health = { status: string; db: string };

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API_URL}/health`);
  // /health responde 503 con cuerpo JSON cuando la base cae: se muestra igual.
  return res.json();
}
