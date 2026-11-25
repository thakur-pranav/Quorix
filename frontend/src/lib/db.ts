import "server-only";

import mongoose from "mongoose";

import { getEnv } from "@/lib/env";

type MongooseCache = { conn: typeof mongoose | null; promise: Promise<typeof mongoose> | null };

/**
 * One connection per server process. In development, hot reload re-runs this module, so the
 * cache lives on `globalThis`; without it every edit would open another connection pool.
 * Caching the *promise* too means parallel requests during startup share one connect().
 */
const globalWithMongoose = globalThis as typeof globalThis & { _mongoose?: MongooseCache };
const cache = (globalWithMongoose._mongoose ??= { conn: null, promise: null });

export async function connectDB(): Promise<typeof mongoose> {
  if (cache.conn) return cache.conn;
  cache.promise ??= mongoose.connect(getEnv().MONGODB_URI, {
    bufferCommands: false, // fail fast instead of queueing queries while disconnected
    serverSelectionTimeoutMS: 5000,
  });
  try {
    cache.conn = await cache.promise;
  } catch (error) {
    cache.promise = null; // let the next request retry instead of reusing a failed promise
    throw error;
  }
  return cache.conn;
}
