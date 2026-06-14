# Sample generated training code to check against examples/cards/zhou2023thyroid__MedSAM-ft.json
batch_size = 8  # honors the card (8 per GPU)

for x, y in train_loader:
    pred = model(x)
    loss = criterion(pred, y)
    loss.backward()

# evaluation: intensity jitter applied ONLY at eval, as the paper requires
if phase == "eval":
    x = intensity_jitter(x, strength=0.1)
    pred = model(x)
