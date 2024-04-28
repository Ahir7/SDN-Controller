const express = require("express");
const bodyParser = require("body-parser");
const userRouter = require("../Router/userRouter");
const cors = require('cors');
const app = express();

const PORT = 5500;

app.use(cors());
app.use(bodyParser.json());

app.use("/api", userRouter);

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
