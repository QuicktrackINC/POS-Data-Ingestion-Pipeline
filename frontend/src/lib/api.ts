export async function login(username: string, password: string): Promise<{ access_token: string }> {
  throw new Error("Local login is disabled. Please login via QuickTrack Hub.");
}
