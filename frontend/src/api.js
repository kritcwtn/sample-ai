import axios from 'axios';

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:4000';
const AI = import.meta.env.VITE_AI_URL || 'http://localhost:8000';

export const backend = axios.create({ baseURL: BACKEND });
export const ai = axios.create({ baseURL: AI });

export const listProducts = (params = {}) =>
    backend.get('/products', { params }).then((r) => r.data);

export const addProduct = (payload) =>
    backend.post('/products', payload).then((r) => r.data);

export const updateProduct = (id, patch) =>
    backend.put(`/products/${id}`, patch).then((r) => r.data);

export const sellProduct = (id, amount = 1) =>
    backend.post(`/products/${id}/sell`, { amount }).then((r) => r.data);

export const getStats = () => backend.get('/stats').then((r) => r.data);
export const listBrands = () => backend.get('/brands').then((r) => r.data);
export const listCategories = () => backend.get('/categories').then((r) => r.data);
export const listWarehouses = () => backend.get('/warehouses').then((r) => r.data);

export const askAI = (question) =>
    ai.post('/chat', { question }).then((r) => r.data);
