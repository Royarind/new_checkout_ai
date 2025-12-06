# Install React Router DOM

The npm install failed due to PowerShell execution policy. 

**To install manually, run ONE of these:**

### Option 1: Use cmd instead of PowerShell
```cmd
cd frontend
npm install react-router-dom
```

### Option 2: Fix PowerShell execution policy
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
cd frontend
npm install react-router-dom
```

### Option 3: Use npx
```powershell
cd frontend
npx npm install react-router-dom
```

Then start the frontend:
```bash
npm run dev
```
