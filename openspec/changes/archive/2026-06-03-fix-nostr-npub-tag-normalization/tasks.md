## 1. Update Nostr tag handling

- [x] 1.1 Add normalization for recipient `p` tags so `npub...` values are converted to hex before publish.
- [x] 1.2 Preserve raw hex recipient values without modification.
- [x] 1.3 Keep non-`p` tags unchanged.

## 2. Update documentation

- [x] 2.1 Update the Nostr capability spec to state that recipient tags accept either `npub` or raw hex.
- [x] 2.2 Add or update the inline code comment/example showing both accepted recipient key formats.

## 3. Verify behavior

- [x] 3.1 Add a regression test for `npub` recipient tag normalization.
- [x] 3.2 Run the Nostr test suite and confirm the fix does not break existing hex-based publishing.
