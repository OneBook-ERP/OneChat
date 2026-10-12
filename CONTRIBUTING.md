# Contributing to OneChat

1. Fork the [OneChat repository](https://github.com/OneBook-ERP/OneChat) on GitHub.
2. Go to the `apps/onechat` folder of your bench and run `git pull --unshallow` so you have the full history.
3. Create a branch from `develop`, for example `git checkout -b fix-inbox-search`.
4. Make your changes.
5. Run `bench start`, and `yarn dev` in `apps/onechat/frontend` for the interface, and check that your changes work.
6. Commit with a clear message, for example `fix: inbox search ignores archived chats`.
7. Push the branch to your fork and open a pull request against `develop`.

To report a bug or suggest a feature, [open an issue](https://github.com/OneBook-ERP/OneChat/issues/new).
