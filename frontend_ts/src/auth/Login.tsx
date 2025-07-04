import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import logo from "../assets/Primary_Mark_500px_500px.png";
import { GoogleLogo, MicrosoftLogo } from "./SocialAuthLogos";
import { useState } from "react";
import {
  AuthError,
  signInWithEmailAndPassword,
  AuthErrorCodes,
} from "firebase/auth";
import { auth } from "./BaseAuth";
import { Navigate } from "react-router";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { handleGoogleSignIn } from "./GoogleAuth";
import { useAuthContext } from "./AuthProvider";

export function Login() {
  const { firebaseUser } = useAuthContext();
  if (firebaseUser) {
    // User is logged in already.
    return <Navigate to="/accounts" />;
  }
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const formSchema = z.object({
    email: z.string().min(1).email(),
    password: z.string().min(8),
  });
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const handleLogin = async (inputDetails: z.infer<typeof formSchema>) => {
    const email = inputDetails.email;
    const password = inputDetails.password;
    try {
      await signInWithEmailAndPassword(auth, email, password);
      // Successful login!
      setErrorMessage(null);
    } catch (error) {
      // Ensure the error is properly typed as Firebase's AuthError
      const firebaseError = error as AuthError;
      const errorCode = firebaseError.code;
      const errorMessage = firebaseError.message;
      if (errorCode === AuthErrorCodes.INVALID_LOGIN_CREDENTIALS) {
        setErrorMessage("Invalid Login Credentials");
      } else if (errorCode === AuthErrorCodes.EMAIL_EXISTS) {
        setErrorMessage("Email already in use with existing account");
      } else if (errorCode === AuthErrorCodes.NETWORK_REQUEST_FAILED) {
        setErrorMessage(
          "You are offline right now, please try again after you are online."
        );
      }
      console.error("Login Error:", errorCode);
      console.error("login message: ", errorMessage);
    }
  };

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl flex flex-col gap-6">
        <Card className="overflow-hidden">
          <CardContent className="grid p-0 md:grid-cols-2">
            {/* Login using Email and Password */}
            <div className="p-6 md:p-8">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(handleLogin)}>
                  <div className="flex flex-col gap-6">
                    <div className="flex flex-col items-center text-center">
                      <h1 className="text-2xl font-bold">Welcome back</h1>
                      <p className="text-balance text-muted-foreground">
                        Login to your Userport account
                      </p>
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
                                placeholder="m@example.com"
                                className="border-gray-300 border-0 rounded-md"
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
                            <FormDescription></FormDescription>
                            <FormControl>
                              <Input
                                type="password"
                                placeholder="password"
                                className="border-gray-300 border-0 rounded-md"
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
                      Login
                    </Button>
                  </div>
                </form>
              </Form>

              {/* Social Login Options */}
              <div className="flex flex-col gap-6 mt-6">
                <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border">
                  <span className="relative z-10 bg-background px-2 text-muted-foreground">
                    Or continue with
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Button
                    variant="outline"
                    className="w-full hover:bg-gray-100"
                    onClick={() => handleGoogleSignIn()}
                  >
                    <GoogleLogo />
                    <span className="sr-only">Login with Google</span>
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full hover:bg-gray-100"
                  >
                    <MicrosoftLogo />
                    <span className="sr-only">Login with Microsoft</span>
                  </Button>
                </div>
                <div className="text-center text-sm">
                  Don&apos;t have an account?{" "}
                  <a href="/signup" className="underline underline-offset-4">
                    Sign up
                  </a>
                </div>
              </div>
            </div>

            {/* Userport Logo Image */}
            <div className="relative hidden md:block bg-gray-50">
              <img
                src={logo}
                alt="Userport Logo"
                className="absolute inset-0 w-full object-cover dark:brightness-[0.2] dark:grayscale"
              />
            </div>
          </CardContent>
        </Card>
        <div className="text-balance text-center text-xs text-muted-foreground [&_a]:underline [&_a]:underline-offset-4 hover:[&_a]:text-primary">
          By clicking continue, you agree to our{" "}
          <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>.
        </div>
      </div>
    </div>
  );
}
