const express = require('express');
const router = express.Router();
const userResister = require('../Controller/userController')

router.route('/resister').post(userResister.registerUser);
router.route('/login').post(userResister.login);

module.exports = router;
