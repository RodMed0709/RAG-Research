# Violating version: wrong batch size, and jitter applied during TRAINING (wrong phase).
batch_size = 16  # VIOLATES the card (should be 8)

for x, y in train_loader:
    x = intensity_jitter(x, strength=0.1)  # jitter in the TRAINING loop (card requires eval-only)
    loss = criterion(model(x), y)
    loss.backward()
