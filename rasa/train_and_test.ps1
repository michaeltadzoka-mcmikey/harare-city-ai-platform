Write-Output "🚀 HARARE MUNICIPAL CHATBOT - RASA TRAINING SCRIPT"
Write-Output "=================================================="

# Step 1: Validate configuration
Write-Output "Step 1: Validating RASA configuration..."
rasa data validate --domain domain.yml --data data/
if ($LASTEXITCODE -ne 0) {
    Write-Output "❌ Configuration validation failed!"
    exit 1
}
Write-Output "✅ Configuration validated successfully!"

# Step 2: Train the model
Write-Output "Step 2: Training RASA model..."
rasa train --domain domain.yml --config config.yml --data data/ --out models/
if ($LASTEXITCODE -ne 0) {
    Write-Output "❌ Training failed!"
    exit 1
}
Write-Output "✅ Model trained successfully!"

# Step 3: Run tests
if (Test-Path "tests/test_stories.yml") {
    Write-Output "Step 3: Running test stories..."
    rasa test --stories tests/test_stories.yml --out results/
    Write-Output "✅ Tests completed! Check results/ directory for details."
} else {
    Write-Output "⚠️ No test stories found. Skipping tests."
}

# Step 4: Show model info
Write-Output "📊 Model Information:"
$latestModel = Get-ChildItem "models/*.tar.gz" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($null -ne $latestModel) {
    Write-Output "Latest model: $($latestModel.Name)"
} else {
    Write-Output "❌ Error: No trained model found in the models directory."
}