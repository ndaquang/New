// Lưu danh thiếp trong IndexedDB của Safari (dữ liệu nằm trên iPhone).
(function (root) {
  'use strict';
  const DB_NAME = 'danh-thiep';
  const STORE = 'cards';
  let dbPromise = null;

  function open() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const store = req.result.createObjectStore(STORE, { keyPath: 'id' });
        store.createIndex('createdAt', 'createdAt');
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  async function tx(mode, fn) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      const store = t.objectStore(STORE);
      let result;
      Promise.resolve(fn(store)).then((r) => (result = r));
      t.oncomplete = () => resolve(result);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  }

  function reqToPromise(req) {
    return new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  const CardDB = {
    async all() {
      const db = await open();
      const items = await reqToPromise(db.transaction(STORE).objectStore(STORE).getAll());
      return items.sort((a, b) => b.createdAt - a.createdAt);
    },
    async get(id) {
      const db = await open();
      return reqToPromise(db.transaction(STORE).objectStore(STORE).get(id));
    },
    put(card) {
      return tx('readwrite', (s) => s.put(card));
    },
    remove(id) {
      return tx('readwrite', (s) => s.delete(id));
    },
    clear() {
      return tx('readwrite', (s) => s.clear());
    },
  };

  root.CardDB = CardDB;
})(self);
