const mongoose = require("mongoose");
const bcrypt = require("bcrypt");

const username = "jaypatelll573";
const password = "jay@1234";
const clusterName = "cluster0";
const databaseName = "SDN_CONTROLLER";

const uri = `mongodb+srv://jaypatelll573:${encodeURIComponent(password)}@${clusterName}.vwx601l.mongodb.net/${databaseName}?retryWrites=true&w=majority`;

mongoose.connect(uri)
  .then(() => {
    console.log("Connection to MongoDB successful.");
  })
  .catch((error) => {
    console.error("Error connecting to MongoDB:", error);
    process.exit(1);
  });

const userSchema = new mongoose.Schema({
  name: {
    type: String,
    required: true
  },
  email: {
    type: String,
    required: true,
    unique: true
  },
  password: {
    type: String,
    required: true
  }
});


userSchema.pre('save', async function (next) {
  try {
    const user = this;
    if (!user.isModified('password')) return next();

    const hashedPassword = await bcrypt.hash(user.password, 10);
    user.password = hashedPassword;
    next();
  } catch (error) {
    return next(error);
  }
});

const User = mongoose.model("User", userSchema);

module.exports = User;
