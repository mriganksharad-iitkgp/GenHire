$srcDir = "d:\HR Tech\product-prototyping-lab\react-frontend\src"

$files = @(
    "pages\Profile.jsx",
    "pages\Practice.jsx",
    "pages\JobDetails.jsx",
    "pages\Chat.jsx",
    "pages\ApplicationView.jsx",
    "pages\AdminDashboard.jsx",
    "pages\admin\CandidateDetail.jsx",
    "pages\candidate\CandidateCostStatistics.jsx",
    "pages\recruiter\RecruiterCostStatistics.jsx",
    "components\recruiter\CandidateCard.jsx",
    "components\candidate\CVList.jsx",
    "components\CVViewer.jsx",
    "components\CVSelectionModal.jsx"
)

foreach ($f in $files) {
    $path = Join-Path $srcDir $f
    if (-not (Test-Path $path)) {
        Write-Host "SKIP (not found): $f"
        continue
    }
    
    $content = [System.IO.File]::ReadAllText($path)
    $original = $content
    
    # Determine relative import path based on depth
    $depth = ($f -split '\\').Count - 1
    $prefix = "../" * $depth
    $importPath = $prefix + "utils/sessionManager"
    
    # Add import if not already present
    if ($content -notmatch "sessionManager") {
        $importLine = "import { getToken, getUser, clearSession, isLoggedIn } from ""$importPath"";"
        
        # Find last import line index
        $lines = $content -split "`r`n"
        $lastImportIdx = -1
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "^\s*import ") {
                $lastImportIdx = $i
            }
        }
        
        if ($lastImportIdx -ge 0) {
            $linesList = [System.Collections.ArrayList]::new($lines)
            $linesList.Insert($lastImportIdx + 1, $importLine)
            $content = $linesList -join "`r`n"
        }
    }
    
    # Replace token reads
    $content = $content -replace "localStorage\.getItem\(`"companyxyz-token`"\)", "getToken()"
    $content = $content -replace "localStorage\.getItem\('companyxyz-token'\)", "getToken()"
    $content = $content -replace 'localStorage\.getItem\(process\.env\.REACT_APP_TOKEN_KEY \|\| "companyxyz-token"\)', "getToken()"
    $content = $content -replace "localStorage\.getItem\(process\.env\.REACT_APP_TOKEN_KEY \|\| 'companyxyz-token'\)", "getToken()"
    
    # Replace user reads
    $content = $content -replace "localStorage\.getItem\(`"companyxyz-user`"\)", "getUser()"
    $content = $content -replace "localStorage\.getItem\('companyxyz-user'\)", "getUser()"
    $content = $content -replace 'localStorage\.getItem\(process\.env\.REACT_APP_USER_KEY \|\| "companyxyz-user"\)', "getUser()"
    $content = $content -replace "localStorage\.getItem\(process\.env\.REACT_APP_USER_KEY \|\| 'companyxyz-user'\)", "getUser()"
    $content = $content -replace "localStorage\.getItem\(process\.env\.REACT_APP_USER_KEY\)", "getUser()"
    
    # Replace removeItem for token
    $content = $content -replace 'localStorage\.removeItem\(process\.env\.REACT_APP_TOKEN_KEY \|\| "companyxyz-token"\)', "clearSession()"
    $content = $content -replace "localStorage\.removeItem\(`"companyxyz-token`"\)", "clearSession()"
    $content = $content -replace "localStorage\.removeItem\('companyxyz-token'\)", "clearSession()"
    
    # Remove orphan removeItem for user key (clearSession handles both)
    $content = $content -replace '\s*localStorage\.removeItem\(process\.env\.REACT_APP_USER_KEY \|\| "companyxyz-user"\);\r?\n', "`r`n"
    $content = $content -replace "\s*localStorage\.removeItem\(`"companyxyz-user`"\);\r?\n", "`r`n"
    
    if ($content -ne $original) {
        [System.IO.File]::WriteAllText($path, $content)
        Write-Host "UPDATED: $f"
    } else {
        Write-Host "NO CHANGE: $f"
    }
}

Write-Host "`nDone!"
