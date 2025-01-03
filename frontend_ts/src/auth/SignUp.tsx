import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import logo from "../assets/Primary_Mark_500px_500px.png";
import { GoogleLogo, MicrosoftLogo } from "./SocialAuthLogos";
import { useAuthContext } from "./AuthProvider";
import { Navigate } from "react-router";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { handleGoogleSignIn } from "./GoogleAuth";
import { createUserWithEmailAndPassword, updateProfile, AuthError, AuthErrorCodes } from "firebase/auth";
import { auth } from "./BaseAuth";
import { useState } from "react";

export function SignUp() {
  const user = useAuthContext();
  if (user) {
    // User is logged in already, redirect to app.
    return <Navigate to="/accounts" />;
  }
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const formSchema = z.object({
    firstName: z.string().min(1),
    lastName: z.string().min(1),
    email: z.string().min(1).email(),
    password: z.string().min(8),
  });
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      firstName: "",
      lastName: "",
      email: "",
      password: "",
    },
  });

  const handleSignUp = async (inputDetails: z.infer<typeof formSchema>) => {
    const firstName = inputDetails.firstName;
    const lastName = inputDetails.lastName;
    const email = inputDetails.email;
    const password = inputDetails.password;
    try {
      const userCredential = await createUserWithEmailAndPassword(
        auth,
        email,
        password
      );
      const user = userCredential.user;

      // Update display Name.
      const displayName = `${firstName} ${lastName}`;
      await updateProfile(user, { displayName: displayName });

      setErrorMessage(null);
    } catch (error) {
       // Ensure the error is properly typed as Firebase's AuthError
            const firebaseError = error as AuthError;
      const errorCode = firebaseError.code;
      const errorMessage = firebaseError.message;
      if (errorCode === AuthErrorCodes.EMAIL_EXISTS) {
        setErrorMessage("Email already in use with existing account");
      } else if (errorCode === AuthErrorCodes.NETWORK_REQUEST_FAILED) {
        setErrorMessage(
          "You are offline right now, please try again after you are online."
        );
      } else if (errorCode === AuthErrorCodes.TOO_MANY_ATTEMPTS_TRY_LATER) {
        setErrorMessage("Too many requests, try again in a bit.");
      }
      console.error("Sign Up Error Code:", errorCode);
      console.error("Sign Up Error Message: ", errorMessage);
    }
  };

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl flex flex-col gap-6">
        <Card className="overflow-hidden">
          <CardContent className="grid p-0 md:grid-cols-2">
            {/* Sign up manually */}
            <div className="p-6 md:p-8">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(handleSignUp)}>
                  <div className="flex flex-col gap-6">
                    <div className="flex flex-col items-center text-center">
                      <h1 className="text-2xl font-bold">Create an account</h1>
                      <p className="text-balance text-muted-foreground">
                        Sign up for your Userport account
                      </p>
                    </div>
                    <div className="grid gap-2">
                      <FormField
                        control={form.control}
                        name="firstName"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="text-gray-800">
                              First Name
                            </FormLabel>
                            <FormDescription className="text-gray-500 text-sm"></FormDescription>
                            <FormControl>
                              <Input
                                placeholder="John"
                                className="border-0 rounded-md"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="grid gap-2">
                      <FormField
                        control={form.control}
                        name="lastName"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="text-gray-800">
                              Last Name
                            </FormLabel>
                            <FormDescription className="text-gray-500 text-sm"></FormDescription>
                            <FormControl>
                              <Input
                                placeholder="Doe"
                                className="border-0 rounded-md"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="grid gap-2">
                      <FormField
                        control={form.control}
                        name="email"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="text-gray-800">
                              Email
                            </FormLabel>
                            <FormDescription></FormDescription>
                            <FormControl>
                              <Input
                                className="border-0 rounded-md"
                                placeholder="m@example.com"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    <div className="grid gap-2">
                      <FormField
                        control={form.control}
                        name="password"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="text-gray-800">
                              Password
                            </FormLabel>
                            <FormDescription className="text-gray-500 text-sm"></FormDescription>
                            <FormControl>
                              <Input
                                type="password"
                                placeholder="password"
                                className="border-0 rounded-md"
                                autoComplete="new-password"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                    {errorMessage && (
                      <p className="text-sm  text-destructive">
                        {errorMessage}
                      </p>
                    )}
                    <Button type="submit" className="w-full">
                      Sign Up
                    </Button>
                  </div>
                </form>
              </Form>

              {/* Social Sign Up */}
              <div className="flex flex-col gap-6 mt-6">
                <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border">
                  <span className="relative z-10 bg-background px-2 text-muted-foreground">
                    Or sign up with
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Button
                    variant="outline"
                    className="w-full hover:bg-gray-100"
                    onClick={() => handleGoogleSignIn()}
                  >
                    <GoogleLogo />
                    <span className="sr-only">Sign up with Google</span>
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full hover:bg-gray-100"
                  >
                    <MicrosoftLogo />
                    <span className="sr-only">Sign up with Microsoft</span>
                  </Button>
                </div>
                <div className="text-center text-sm">
                  Already have an account?{" "}
                  <a href="/login" className="underline underline-offset-4">
                    Login
                  </a>
                </div>
              </div>
            </div>

            {/* Userport Logo Image */}
            <div className="relative hidden md:block bg-gray-50">
              <img
                src={logo}
                alt="Userport Logo"
                className="absolute inset-0 top-20 w-full object-cover dark:brightness-[0.2] dark:grayscale"
              />
            </div>
          </CardContent>
        </Card>
        <div className="text-balance text-center text-xs text-muted-foreground [&_a]:underline [&_a]:underline-offset-4 hover:[&_a]:text-primary">
          By clicking Sign Up, you agree to our <a href="#">Terms of Service</a>{" "}
          and <a href="#">Privacy Policy</a>.
        </div>
      </div>
    </div>
  );
}
