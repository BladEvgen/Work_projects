document.addEventListener("DOMContentLoaded", function() {
  const passwordInput = document.getElementById("password");
  const confirmPasswordInput = document.getElementById("confirm_password");
  const registerBtn = document.getElementById("registerBtn");
  const firstNameInput = document.getElementById("first_name");
  const lastNameInput = document.getElementById("last_name");
  const passwordHelp = document.getElementById("passwordHelp");
  const confirmPasswordHelp = document.getElementById("confirmPasswordHelp");
  const togglePasswordBtns = document.querySelectorAll("#togglePassword");
  const passwordStrength = document.getElementById("passwordStrength");
  const passwordTip = document.getElementById("passwordTip");

  function validateForm() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const firstName = firstNameInput.value.trim();
    const lastName = lastNameInput.value.trim();
    let isValid = true;

    if (!password && !confirmPassword && !firstName && !lastName) {
      registerBtn.disabled = true;
      passwordStrength.style.width = "0%";
      passwordHelp.textContent = "";
      passwordTip.textContent = "";
      confirmPasswordHelp.textContent = "";
      return;
    }

    if (password || confirmPassword) {
      if (password !== confirmPassword) {
        confirmPasswordHelp.textContent = "Passwords do not match.";
        isValid = false;
      } else {
        confirmPasswordHelp.textContent = "";
      }

      const minLength = 8;
      const isLengthValid = password.length >= minLength;
      const conditions = [
        { regex: /[A-Z]/, fulfilled: false },
        { regex: /[a-z]/, fulfilled: false },
        { regex: /\d/, fulfilled: false },
        { regex: /[#!?@$%^&*-]/, fulfilled: false },
      ];

      conditions.forEach(function(condition) {
        condition.fulfilled = condition.regex.test(password);
      });

      const fulfilledConditions = conditions.reduce(function(count, condition) {
        return count + (condition.fulfilled ? 1 : 0);
      }, 0);

      let strength = (fulfilledConditions / conditions.length) * 100;

      if (!isLengthValid) {
        strength = 30;
      }

      passwordStrength.style.width = strength + "%";
      passwordStrength.classList.remove("bg-danger", "bg-warning", "bg-success");

      if (strength < 33) {
        passwordStrength.classList.add("bg-danger");
        passwordHelp.textContent = "Weak password ";
        passwordTip.textContent = "Для более надежного пароля используйте сочетание прописных и строчных букв, цифр и специальных символов (#?!@$%^&*-). Убедитесь, что его длина не менее 8 символов.";
        isValid = false;
      } else if (strength < 76) {
        passwordStrength.classList.add("bg-warning");
        passwordHelp.textContent = "Medium strength password ";
        passwordTip.textContent = "Для более надежного пароля используйте сочетание прописных и строчных букв, цифр и специальных символов (#?!@$%^&*-). Убедитесь, что его длина не менее 8 символов.";
        isValid = false;
      } else {
        passwordStrength.classList.add("bg-success");
        passwordHelp.textContent = "Strong password";
        passwordTip.textContent = "";
      }
    }


    if (isValid && (firstName || lastName || (password && confirmPassword))) {
      registerBtn.disabled = false;
    } else {
      registerBtn.disabled = true;
    }
  }

  function togglePasswordsVisibility() {
    const type = passwordInput.type === "password" ? "text" : "password";
    passwordInput.type = type;
    confirmPasswordInput.type = type;
    togglePasswordBtns.forEach(btn => {
      const icon = btn.querySelector("i");
      if (type === "text") {
        icon.classList.remove("fa-eye");
        icon.classList.add("fa-eye-slash");
      } else {
        icon.classList.remove("fa-eye-slash");
        icon.classList.add("fa-eye");
      }
    });
  }

  passwordInput.addEventListener("input", validateForm);
  confirmPasswordInput.addEventListener("input", validateForm);
  firstNameInput.addEventListener("input", validateForm);
  lastNameInput.addEventListener("input", validateForm);
  togglePasswordBtns.forEach(btn => btn.addEventListener("click", togglePasswordsVisibility));

  validateForm();
});
