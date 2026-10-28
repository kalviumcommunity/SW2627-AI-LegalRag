import { apiClient, setAuthToken } from './client';
import type { TokenResponse, User, UserLoginRequest, UserRegisterRequest } from './types';

export const authApi = {
  /**
   * Register a new user account.
   */
  async register(data: UserRegisterRequest): Promise<TokenResponse> {
    const response = await apiClient<TokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setAuthToken(response.access_token);
    return response;
  },

  /**
   * Login with email and password.
   */
  async login(data: UserLoginRequest): Promise<TokenResponse> {
    const response = await apiClient<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setAuthToken(response.access_token);
    return response;
  },

  /**
   * Fetch current authenticated user profile.
   */
  async me(): Promise<User> {
    return apiClient<User>('/auth/me', {
      method: 'GET',
    });
  },

  /**
   * Clear session token.
   */
  logout(): void {
    setAuthToken(null);
  },
};
