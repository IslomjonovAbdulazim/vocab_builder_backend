# VocabBuilder Auth API

Crystal clear authentication API for VocabBuilder mobile app.

## Features

✅ **Register** - Create new account with email verification  
✅ **Login** - Secure login with JWT tokens  
✅ **Verify Email** - OTP-based email verification  
✅ **Forgot Password** - Password reset via email  
✅ **Reset Password** - Secure password reset  
✅ **User Profile** - Get user information  

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   - Copy your Resend API key to `.env`
   - Update `SECRET_KEY` in `.env`

3. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

4. **View API docs:**
   - http://localhost:8000/docs
   - http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login  
- `POST /auth/verify-email` - Verify email with OTP
- `POST /auth/forgot-password` - Request password reset
- `POST /auth/reset-password` - Reset password

### Users  
- `GET /auth/profile` - Get user profile (requires JWT)

## Email Templates

Beautiful HTML emails with:
- 📚 VocabBuilder branding
- 🎨 Modern gradient design
- 📱 Mobile-responsive layout
- 🔒 Security warnings
- ⏱️ Expiration notices

## Flow Examples

### Registration Flow
```
1. POST /auth/register → Creates unverified user + sends OTP
2. POST /auth/verify-email → Verifies OTP + returns JWT token
```

### Login Flow  
```
1. POST /auth/login → 
   - If verified: Returns JWT token
   - If unverified: Sends new OTP + redirects to verify
```

### Password Reset Flow
```
1. POST /auth/forgot-password → Sends reset OTP
2. POST /auth/verify-email → Verify reset OTP  
3. POST /auth/reset-password → Reset password + return JWT
```

## Security Features

🔒 **Password Hashing** - bcrypt with salt  
🔑 **JWT Tokens** - 100-day expiration  
⏰ **OTP Expiration** - 5-minute validity  
🧹 **Auto Cleanup** - Removes expired OTPs and unverified users  
📧 **Email Validation** - Pydantic email validation  
🛡️ **CORS Protection** - Configurable origins  

## Database

- **SQLite** for simplicity
- **Auto-created** tables on startup
- **Two tables**: `users` and `otps`

## Response Format

All endpoints return consistent format:
```json
{
  "status_code": 200,
  "details": "Success message",
  "is_success": true,
  "token": "jwt_token_here"
}
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# View logs
tail -f app.log
```

## Deployment

Ready for deployment to:
- ✅ Timeweb.cloud  
- ✅ Railway
- ✅ Heroku
- ✅ Any VPS

## Environment Variables

```bash
DATABASE_URL=sqlite:///./database/vocabbuilder.db
SECRET_KEY=your-super-secret-jwt-key-change-this
RESEND_API_KEY=re_your_resend_api_key
FROM_EMAIL=onboarding@resend.dev
FROM_NAME=VocabBuilder
ACCESS_TOKEN_EXPIRE_DAYS=100
OTP_EXPIRE_MINUTES=5
```

---

**Built with ❤️ for VocabBuilder**