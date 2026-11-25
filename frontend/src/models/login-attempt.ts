import "server-only";

import { model, models, type Model, Schema } from "mongoose";

/** Login rate limiting: one document per FAILED login, deleted by MongoDB after 15 minutes. */
export const LOGIN_WINDOW_SECONDS = 15 * 60;
export const MAX_FAILED_LOGINS = 5;

const loginAttemptSchema = new Schema({
  email: { type: String, required: true, lowercase: true, index: true },
  // TTL index: MongoDB's background job removes documents once they are this old.
  // It runs about once a minute, so queries also filter by time to be exact.
  createdAt: { type: Date, default: Date.now, expires: LOGIN_WINDOW_SECONDS },
});

type LoginAttemptFields = { email: string; createdAt: Date };

export const LoginAttempt: Model<LoginAttemptFields> =
  (models.LoginAttempt as Model<LoginAttemptFields> | undefined) ??
  model<LoginAttemptFields>("LoginAttempt", loginAttemptSchema);
