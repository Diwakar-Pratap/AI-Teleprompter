import crypto from "crypto";

/**
 * SecurityManager — handles security-related operations in the main process.
 *
 * Responsibilities:
 * - Generate and store the backend auth token (in-memory only)
 * - Validate file paths and inputs
 * - Provide secure token access for backend connection
 */
export class SecurityManager {
  /** Auth token for WebSocket/API access — generated fresh on each startup */
  private readonly backendToken: string;

  constructor() {
    // Generate a secure random token for this session
    this.backendToken = crypto.randomBytes(32).toString("hex");
  }

  /**
   * Get the backend auth token.
   * This is safe to pass to the Python backend but NOT to the renderer.
   */
  getBackendToken(): string {
    return this.backendToken;
  }

  /**
   * Validate that a file path is safe (no path traversal, absolute, etc.)
   */
  validateFilePath(filePath: string): boolean {
    if (!filePath || typeof filePath !== "string") return false;
    // No path traversal
    if (filePath.includes("..")) return false;
    // Must be absolute
    if (!filePath.match(/^[A-Za-z]:\\/)) return false;
    // No null bytes
    if (filePath.includes("\0")) return false;
    return true;
  }

  /**
   * Validate allowed file extensions.
   */
  validateFileExtension(filePath: string, allowedExtensions: string[]): boolean {
    const lower = filePath.toLowerCase();
    return allowedExtensions.some((ext) => lower.endsWith(ext.toLowerCase()));
  }
}
