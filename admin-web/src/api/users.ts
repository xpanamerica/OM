import { http } from "./http";

export type UserMe = {
  id: string;
  email: string;
  username: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
};

export async function fetchMe(): Promise<UserMe> {
  const { data } = await http.get<UserMe>("/users/me");
  return data;
}
