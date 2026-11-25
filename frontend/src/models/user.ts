import "server-only";

import { type InferSchemaType, model, models, type Model, Schema } from "mongoose";

const userSchema = new Schema(
  {
    name: { type: String, required: true, trim: true, maxlength: 80 },
    email: { type: String, required: true, unique: true, lowercase: true, trim: true },
    // select: false → never loaded unless a query asks for it explicitly (+passwordHash).
    passwordHash: { type: String, required: true, select: false },
    organizationName: { type: String, required: true, trim: true, maxlength: 120 },
    // Generated on the server at signup; the tenant id FastAPI trusts via the signed token.
    organizationId: { type: String, required: true, index: true },
  },
  { timestamps: true },
);

type UserFields = InferSchemaType<typeof userSchema>;

export const User: Model<UserFields> =
  (models.User as Model<UserFields> | undefined) ?? model<UserFields>("User", userSchema);

/** What the rest of the app (and the browser) may see. Never includes the password hash. */
export type SafeUser = {
  id: string;
  name: string;
  email: string;
  organizationName: string;
  organizationId: string;
};

export function toSafeUser(doc: UserFields & { _id: unknown }): SafeUser {
  return {
    id: String(doc._id),
    name: doc.name,
    email: doc.email,
    organizationName: doc.organizationName,
    organizationId: doc.organizationId,
  };
}
