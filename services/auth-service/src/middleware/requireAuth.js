/**
 * src/middleware/requireAuth.js
 * ----------------------------
 * JWT verification middleware for Express.
 * Other services can import this module and use it to protect their routes.
 *
 * Usage:
 *   const requireAuth = require('@mplads/auth-service/src/middleware/requireAuth');
 *
 *   // Any authenticated official:
 *   router.get('/protected', requireAuth(), handler);
 *
 *   // Only admins:
 *   router.delete('/admin-only', requireAuth('admin'), handler);
 *
 * The middleware reads the JWT from:
 *   1. httpOnly cookie named "mplads_auth" (primary, set by /auth/verify-otp)
 *   2. Authorization: Bearer <token> header (for API-to-API calls)
 *
 * On success, req.official is set to { id, email, role, iat, exp }.
 * On failure, 401 or 403 is returned with a machine-readable error code.
 */

"use strict";

const jwt    = require("jsonwebtoken");
const config = require("../config");

const COOKIE_NAME = "mplads_auth";

/**
 * @param {string|null} requiredRole - if provided, the official must have this role
 * @returns {import('express').RequestHandler}
 */
function requireAuth(requiredRole = null) {
  return function authMiddleware(req, res, next) {
    // 1. Try cookie first, then Authorization header
    let token =
      (req.cookies && req.cookies[COOKIE_NAME]) ||
      extractBearerToken(req.headers.authorization);

    if (!token) {
      return res.status(401).json({
        error:   "UNAUTHENTICATED",
        message: "Authentication required. Please obtain a token via POST /auth/verify-otp.",
      });
    }

    // 2. Verify JWT signature and expiry
    let payload;
    try {
      payload = jwt.verify(token, config.jwt.secret, {
        algorithms: ["HS256"],
      });
    } catch (err) {
      const code =
        err.name === "TokenExpiredError"
          ? "TOKEN_EXPIRED"
          : "TOKEN_INVALID";
      return res.status(401).json({
        error:   code,
        message: err.name === "TokenExpiredError"
          ? "Your session has expired. Please log in again."
          : "Invalid authentication token.",
      });
    }

    // 3. Role check
    if (requiredRole) {
      const allowedRoles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
      if (!allowedRoles.includes(payload.role)) {
        return res.status(403).json({
          error:   "FORBIDDEN",
          message: `This endpoint requires role '${allowedRoles.join(" or ")}'. Your role is '${payload.role}'.`,
        });
      }
    }

    // 4. Attach principal to request and continue
    req.official = {
      ...payload,
      official_id: payload.official_id || payload.id,
      id:          payload.id || payload.official_id,
    };
    next();
  };
}

/**
 * Extract token from "Authorization: Bearer <token>" header.
 * Returns null if header is absent or malformed.
 */
function extractBearerToken(authHeader) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  const token = authHeader.slice(7).trim();
  return token || null;
}

module.exports = requireAuth;
